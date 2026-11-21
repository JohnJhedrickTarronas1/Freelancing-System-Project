from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login,logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Avg, Q, Count, Sum
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from .models import *
from .forms import *
from .decorators import role_required

def home(request):
 qs=Service.objects.filter(is_active=True,provider__verification_status='APPROVED').select_related('provider__user','category').prefetch_related('packages')
 q=request.GET.get('q',''); category=request.GET.get('category',''); max_price=request.GET.get('max_price','')
 if q: qs=qs.filter(Q(title__icontains=q)|Q(description__icontains=q)|Q(provider__user__username__icontains=q))
 if category: qs=qs.filter(category__slug=category)
 if max_price:
  try: qs=qs.filter(packages__price__lte=Decimal(max_price)).distinct()
  except: pass
 return render(request,'home.html',{'services':qs,'categories':Category.objects.all(),'q':q,'category':category,'max_price':max_price})
def register(request):
 form=RegisterForm(request.POST or None)
 if request.method=='POST' and form.is_valid():
  user=form.save(commit=False); user.email=form.cleaned_data['email']; user.phone=form.cleaned_data['phone']; user.role=form.cleaned_data['role']; user.save()
  if user.role=='PROVIDER': ProviderProfile.objects.create(user=user)
  login(request,user); messages.success(request,'Your account is ready.'); return redirect('dashboard')
 return render(request,'form.html',{'form':form,'title':'Create your account','subtitle':'Join ChoreMarket to book or offer local services.'})
@login_required
def dashboard(request):
 u=request.user
 if u.role=='ADMIN':
  context={'users':User.objects.count(),'bookings':Booking.objects.count(),'pending':ProviderProfile.objects.filter(verification_status='PENDING').count(),'disputes':Dispute.objects.filter(status='OPEN').count(),'popular':Category.objects.annotate(total=Count('services')).order_by('-total')[:5],'approvals':ProviderProfile.objects.filter(verification_status='PENDING').select_related('user'),'open_disputes':Dispute.objects.filter(status='OPEN').select_related('booking')}
 elif u.role=='PROVIDER':
  profile=getattr(u,'provider_profile',None)
  context={'profile':profile,'services':profile.services.all() if profile else [],'bookings':Booking.objects.filter(provider=profile).select_related('client','package') if profile else [],'earnings':Payment.objects.filter(booking__provider=profile,status='RELEASED').aggregate(total=Sum('service_fee'))['total'] if profile else 0}
 else: context={'bookings':Booking.objects.filter(client=u).select_related('provider__user','package')}
 return render(request,'dashboard.html',context)
@login_required
@role_required('PROVIDER')
def provider_profile(request):
 profile=request.user.provider_profile; form=ProviderForm(request.POST or None,request.FILES or None,instance=profile)
 if request.method=='POST' and form.is_valid():
  obj=form.save(commit=False); obj.verification_status='PENDING'; obj.save(); messages.success(request,'Profile submitted for admin verification.'); return redirect('dashboard')
 return render(request,'form.html',{'form':form,'title':'Provider verification','subtitle':'Complete your profile and submit your documents for review.'})
@login_required
@role_required('PROVIDER')
def service_create(request):
 profile=request.user.provider_profile
 if profile.verification_status!='APPROVED': messages.error(request,'Your provider profile must be approved before listing services.'); return redirect('dashboard')
 form=ServiceForm(request.POST or None)
 if request.method=='POST' and form.is_valid():
  service=form.save(commit=False); service.provider=profile; service.save(); return redirect('package_create',service.pk)
 return render(request,'form.html',{'form':form,'title':'Add a service','subtitle':'Create a clear service listing. You can add up to three packages.'})
@login_required
@role_required('PROVIDER')
def package_create(request,service_id):
 service=get_object_or_404(Service,pk=service_id,provider__user=request.user); form=PackageForm(request.POST or None)
 if request.method=='POST' and form.is_valid():
  if service.packages.count()>=3: messages.error(request,'A service can have at most three packages.'); return redirect('dashboard')
  obj=form.save(commit=False); obj.service=service; obj.save(); messages.success(request,'Package added.'); return redirect('dashboard')
 return render(request,'form.html',{'form':form,'title':f'Add package: {service.title}','subtitle':'Set the tier, price and estimated duration.'})

def service_detail(request,pk):
 service=get_object_or_404(Service.objects.select_related('provider__user','category').prefetch_related('packages'),pk=pk,is_active=True)
 reviews=Review.objects.filter(reviewee=service.provider.user).select_related('reviewer')
 return render(request,'service_detail.html',{'service':service,'reviews':reviews,'average':reviews.aggregate(v=Avg('stars'))['v']})
@login_required
def book_service(request,package_id):
 package=get_object_or_404(Package.objects.select_related('service__provider__user','service__category'),pk=package_id)
 if request.user.role!='CLIENT': return HttpResponseForbidden('Only clients can book services.')
 form=BookingForm(request.POST or None)
 if request.method=='POST' and form.is_valid():
  start=form.cleaned_data['start_at']; end=start+timedelta(minutes=package.duration_minutes)
  if start<=timezone.now(): form.add_error('start_at','Choose a future date and time.')
  elif BlockedDate.objects.filter(provider=package.service.provider,date=start.date()).exists(): form.add_error('start_at','The provider is unavailable on this date.')
  else:
   with transaction.atomic():
    conflict=Booking.objects.select_for_update().filter(provider=package.service.provider,status__in=Booking.ACTIVE,start_at__lt=end,end_at__gt=start).exists()
    if conflict: form.add_error('start_at','That slot is already booked. Please choose another time.')
    else:
     booking=Booking.objects.create(client=request.user,provider=package.service.provider,package=package,address=form.cleaned_data['address'],special_instructions=form.cleaned_data['special_instructions'],start_at=start,end_at=end,task_details={'budget_amount':str(form.cleaned_data.get('budget_amount') or 0)})
     budget=form.cleaned_data.get('budget_amount') or Decimal('0'); fee=package.price
     Payment.objects.create(booking=booking,service_fee=fee,budget_amount=budget,platform_fee=(fee*Decimal('0.10')).quantize(Decimal('0.01')))
     notify(package.service.provider.user,f'New booking request #{booking.pk}.',f'/bookings/{booking.pk}/')
     messages.success(request,'Booking request created. Mock payment is now held.'); return redirect('booking_detail',booking.pk)
 return render(request,'form.html',{'form':form,'title':f'Book {package.name}','subtitle':f'{package.service.title} · ₱{package.price} · {package.duration_minutes} minutes'})
@login_required
def booking_detail(request,pk):
 booking=get_object_or_404(Booking.objects.select_related('client','provider__user','package__service','payment').prefetch_related('proofs','messages'),pk=pk)
 if request.user not in [booking.client,booking.provider.user] and request.user.role!='ADMIN': return HttpResponseForbidden()
 msgform=MessageForm(request.POST or None); proofform=ProofForm(); reviewform=ReviewForm(); reportform=ReportForm(); disputeform=DisputeForm()
 if request.method=='POST':
  action=request.POST.get('action')
  try:
   if action=='message' and msgform.is_valid():
    m=msgform.save(commit=False); m.booking=booking; m.sender=request.user; m.save(); notify(booking.provider.user if request.user==booking.client else booking.client,'New message on booking.',f'/bookings/{pk}/')
   elif action=='transition': booking.transition(request.POST.get('status'),request.user); messages.success(request,'Booking updated.')
   elif action=='confirm_payment' and request.user==booking.client and booking.status=='COMPLETED': booking.payment.release(); messages.success(request,'Completion confirmed. Mock payment released to the provider.')
   elif action=='proof' and proofform.is_valid() and request.user==booking.provider.user:
    proof=proofform.save(commit=False); proof.booking=booking; proof.save(); messages.success(request,'Proof uploaded.')
   elif action=='review' and booking.status=='COMPLETED' and reviewform.is_valid():
    review=reviewform.save(commit=False); review.booking=booking; review.reviewer=request.user; review.reviewee=booking.provider.user if request.user==booking.client else booking.client; review.save()
   elif action=='report' and reportform.is_valid():
    other=booking.provider.user if request.user==booking.client else booking.client; Report.objects.create(booking=booking,reporter=request.user,reported_user=other,details=reportform.cleaned_data['details']); messages.success(request,'Report submitted to the safety team.')
   elif action=='dispute' and disputeform.is_valid():
    Dispute.objects.create(booking=booking,opened_by=request.user,reason=disputeform.cleaned_data['reason']); booking.transition('DISPUTED',request.user); messages.success(request,'Dispute opened. Payment is frozen for admin review.')
  except (ValidationError,ValueError) as e: messages.error(request,str(e))
  return redirect('booking_detail',pk)
 return render(request,'booking_detail.html',locals())
@login_required
@role_required('ADMIN')
def admin_action(request,kind,pk):
 if request.method!='POST': return redirect('dashboard')
 if kind=='approve':
  profile=get_object_or_404(ProviderProfile,pk=pk); profile.verification_status='APPROVED'; profile.rejection_reason=''; profile.save(); notify(profile.user,'Your provider profile has been verified.')
 elif kind=='reject':
  profile=get_object_or_404(ProviderProfile,pk=pk); profile.verification_status='REJECTED'; profile.rejection_reason=request.POST.get('reason','Please update your documents.'); profile.save(); notify(profile.user,'Your provider application needs changes.')
 elif kind=='resolve':
  dispute=get_object_or_404(Dispute,pk=pk); dispute.status='RESOLVED'; dispute.resolution=request.POST.get('resolution','Reviewed by admin'); dispute.resolved_by=request.user; dispute.save();
  if hasattr(dispute.booking,'payment'): dispute.booking.payment.release()
 return redirect('dashboard')
@login_required
def notifications(request):
 items=request.user.notifications.all(); request.user.notifications.filter(is_read=False).update(is_read=True)
 return render(request,'notifications.html',{'items':items})
@login_required
def logout_view(request): logout(request); return redirect('home')

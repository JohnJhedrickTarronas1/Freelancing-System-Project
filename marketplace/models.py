from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

class User(AbstractUser):
 class Role(models.TextChoices): CLIENT='CLIENT','Client'; PROVIDER='PROVIDER','Service Provider'; ADMIN='ADMIN','Admin'
 role=models.CharField(max_length=12,choices=Role.choices,default=Role.CLIENT)
 phone=models.CharField(max_length=30,blank=True)
 is_suspended=models.BooleanField(default=False)
 @property
 def display_role(self): return self.get_role_display()

class ProviderProfile(models.Model):
 class Verification(models.TextChoices): PENDING='PENDING','Pending'; APPROVED='APPROVED','Approved'; REJECTED='REJECTED','Rejected'
 user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='provider_profile')
 bio=models.TextField(blank=True); base_location=models.CharField(max_length=180,blank=True)
 service_radius_km=models.PositiveIntegerField(default=5)
 id_document=models.FileField(upload_to='private/provider_ids/',blank=True)
 selfie=models.ImageField(upload_to='private/provider_selfies/',blank=True)
 verification_status=models.CharField(max_length=10,choices=Verification.choices,default=Verification.PENDING)
 rejection_reason=models.CharField(max_length=250,blank=True)
 created_at=models.DateTimeField(auto_now_add=True)
 def __str__(self): return self.user.username

class Category(models.Model):
 name=models.CharField(max_length=80,unique=True); slug=models.SlugField(unique=True); description=models.CharField(max_length=200,blank=True)
 icon=models.CharField(max_length=20,default='✦')
 def __str__(self): return self.name

class Service(models.Model):
 provider=models.ForeignKey(ProviderProfile,on_delete=models.CASCADE,related_name='services')
 category=models.ForeignKey(Category,on_delete=models.PROTECT,related_name='services')
 title=models.CharField(max_length=120); description=models.TextField(); is_active=models.BooleanField(default=True)
 created_at=models.DateTimeField(auto_now_add=True)
 def __str__(self): return self.title
 @property
 def starting_price(self): return self.packages.order_by('price').values_list('price',flat=True).first() or 0

class Package(models.Model):
 class Tier(models.TextChoices): BASIC='Basic','Basic'; STANDARD='Standard','Standard'; PREMIUM='Premium','Premium'
 service=models.ForeignKey(Service,on_delete=models.CASCADE,related_name='packages')
 tier=models.CharField(max_length=10,choices=Tier.choices,default=Tier.BASIC)
 name=models.CharField(max_length=80); price=models.DecimalField(max_digits=9,decimal_places=2,validators=[MinValueValidator(0)])
 duration_minutes=models.PositiveIntegerField(default=60); description=models.CharField(max_length=250,blank=True)
 class Meta: ordering=['price']; constraints=[models.UniqueConstraint(fields=['service','tier'],name='unique_service_tier')]
 def __str__(self): return f'{self.service.title} — {self.name}'

class WorkingHours(models.Model):
 provider=models.ForeignKey(ProviderProfile,on_delete=models.CASCADE,related_name='working_hours')
 weekday=models.PositiveSmallIntegerField(choices=[(i,n) for i,n in enumerate(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])])
 start_time=models.TimeField(); end_time=models.TimeField()
 class Meta: ordering=['weekday','start_time']

class BlockedDate(models.Model):
 provider=models.ForeignKey(ProviderProfile,on_delete=models.CASCADE,related_name='blocked_dates')
 date=models.DateField(); reason=models.CharField(max_length=150,blank=True)
 class Meta: constraints=[models.UniqueConstraint(fields=['provider','date'],name='unique_provider_blocked_date')]

class Booking(models.Model):
 class Status(models.TextChoices): PENDING='PENDING','Pending'; CONFIRMED='CONFIRMED','Confirmed'; IN_PROGRESS='IN_PROGRESS','In Progress'; COMPLETED='COMPLETED','Completed'; DECLINED='DECLINED','Declined'; EXPIRED='EXPIRED','Expired'; CANCELLED='CANCELLED','Cancelled'; DISPUTED='DISPUTED','Disputed'
 ACTIVE=[Status.PENDING,Status.CONFIRMED,Status.IN_PROGRESS]
 client=models.ForeignKey(User,on_delete=models.PROTECT,related_name='client_bookings')
 provider=models.ForeignKey(ProviderProfile,on_delete=models.PROTECT,related_name='bookings')
 package=models.ForeignKey(Package,on_delete=models.PROTECT,related_name='bookings')
 address=models.CharField(max_length=250); special_instructions=models.TextField(blank=True)
 task_details=models.JSONField(default=dict,blank=True)
 start_at=models.DateTimeField(); end_at=models.DateTimeField(); status=models.CharField(max_length=15,choices=Status.choices,default=Status.PENDING)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['-created_at']
 def clean(self):
  if self.end_at<=self.start_at: raise ValidationError('End time must be after start time.')
 def overlaps(self):
  return Booking.objects.filter(provider=self.provider,status__in=self.ACTIVE,start_at__lt=self.end_at,end_at__gt=self.start_at).exclude(pk=self.pk).exists()
 def transition(self,new_status,actor):
  allowed={self.Status.PENDING:{self.Status.CONFIRMED,self.Status.DECLINED,self.Status.EXPIRED,self.Status.CANCELLED},self.Status.CONFIRMED:{self.Status.IN_PROGRESS,self.Status.CANCELLED,self.Status.DISPUTED},self.Status.IN_PROGRESS:{self.Status.COMPLETED,self.Status.DISPUTED},self.Status.COMPLETED:{self.Status.DISPUTED}}
  if new_status not in allowed.get(self.status,set()): raise ValidationError('This booking status change is not allowed.')
  if new_status in [self.Status.CONFIRMED,self.Status.DECLINED,self.Status.IN_PROGRESS,self.Status.COMPLETED]:
   if actor.role!='PROVIDER' or actor.pk!=self.provider.user_id: raise ValidationError('Only the assigned provider can perform this action.')
  if new_status==self.Status.CANCELLED and actor not in [self.client,self.provider.user]: raise ValidationError('You cannot cancel this booking.')
  if new_status==self.Status.DISPUTED and actor not in [self.client,self.provider.user] and actor.role!='ADMIN': raise ValidationError('Not permitted.')
  if new_status==self.Status.CONFIRMED and self.overlaps(): raise ValidationError('That time slot is no longer available.')
  if new_status==self.Status.COMPLETED and not self.proofs.filter(kind='PHOTO').exists(): raise ValidationError('Upload at least one completion photo first.')
  if new_status==self.Status.COMPLETED and self.package.service.category.slug=='groceries' and not self.proofs.filter(kind='RECEIPT').exists(): raise ValidationError('Grocery bookings also require a receipt.')
  self.status=new_status; self.save(update_fields=['status'])
  if hasattr(self,'payment'):
   if new_status in [self.Status.DECLINED,self.Status.EXPIRED,self.Status.CANCELLED]: self.payment.refund()
   elif new_status==self.Status.DISPUTED: self.payment.status=Payment.Status.FROZEN; self.payment.save(update_fields=['status'])
  notify(self.client,f'Booking {self.pk} is now {self.get_status_display()}.',f'/bookings/{self.pk}/')
  notify(self.provider.user,f'Booking {self.pk} is now {self.get_status_display()}.',f'/bookings/{self.pk}/')
 def __str__(self): return f'Booking #{self.pk}'

class Payment(models.Model):
 class Status(models.TextChoices): HELD='HELD','Held'; RELEASED='RELEASED','Released'; REFUNDED='REFUNDED','Refunded'; PARTIAL='PARTIAL','Partially refunded'; FROZEN='FROZEN','Frozen'
 booking=models.OneToOneField(Booking,on_delete=models.CASCADE,related_name='payment')
 service_fee=models.DecimalField(max_digits=9,decimal_places=2); budget_amount=models.DecimalField(max_digits=9,decimal_places=2,default=0)
 actual_cost=models.DecimalField(max_digits=9,decimal_places=2,null=True,blank=True); platform_fee=models.DecimalField(max_digits=9,decimal_places=2,default=0)
 status=models.CharField(max_length=10,choices=Status.choices,default=Status.HELD); created_at=models.DateTimeField(auto_now_add=True)
 @property
 def held_total(self): return self.service_fee+self.budget_amount
 def refund(self): self.status=self.Status.REFUNDED; self.save(update_fields=['status'])
 def release(self):
  self.status=self.Status.RELEASED; self.save(update_fields=['status'])

class BookingProof(models.Model):
 booking=models.ForeignKey(Booking,on_delete=models.CASCADE,related_name='proofs')
 kind=models.CharField(max_length=10,choices=[('PHOTO','Photo'),('RECEIPT','Receipt')]); image=models.ImageField(upload_to='proofs/'); caption=models.CharField(max_length=180,blank=True); uploaded_at=models.DateTimeField(auto_now_add=True)

class Message(models.Model):
 booking=models.ForeignKey(Booking,on_delete=models.CASCADE,related_name='messages'); sender=models.ForeignKey(User,on_delete=models.CASCADE)
 body=models.TextField(max_length=2000); sent_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['sent_at']

class Review(models.Model):
 booking=models.ForeignKey(Booking,on_delete=models.CASCADE,related_name='reviews'); reviewer=models.ForeignKey(User,on_delete=models.CASCADE,related_name='written_reviews'); reviewee=models.ForeignKey(User,on_delete=models.CASCADE,related_name='received_reviews')
 stars=models.PositiveSmallIntegerField(validators=[MinValueValidator(1),MaxValueValidator(5)]); comment=models.TextField(blank=True)
 punctuality=models.PositiveSmallIntegerField(null=True,blank=True); politeness=models.PositiveSmallIntegerField(null=True,blank=True)
 class Meta: constraints=[models.UniqueConstraint(fields=['booking','reviewer'],name='one_review_per_booking_direction')]

class Report(models.Model):
 booking=models.ForeignKey(Booking,on_delete=models.CASCADE,related_name='reports'); reporter=models.ForeignKey(User,on_delete=models.CASCADE,related_name='reports_made'); reported_user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='reports_received')
 details=models.TextField(); status=models.CharField(max_length=12,default='OPEN'); created_at=models.DateTimeField(auto_now_add=True)

class Dispute(models.Model):
 booking=models.OneToOneField(Booking,on_delete=models.CASCADE,related_name='dispute'); opened_by=models.ForeignKey(User,on_delete=models.CASCADE); reason=models.TextField(); status=models.CharField(max_length=12,default='OPEN'); resolution=models.TextField(blank=True); resolved_by=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='resolved_disputes'); created_at=models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
 user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='notifications'); message=models.CharField(max_length=250); link=models.CharField(max_length=250,blank=True); is_read=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['-created_at']

def notify(user,message,link=''):
 Notification.objects.create(user=user,message=message,link=link)

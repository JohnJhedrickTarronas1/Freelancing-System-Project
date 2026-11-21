from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import *
class RegisterForm(UserCreationForm):
 email=forms.EmailField(); role=forms.ChoiceField(choices=[('CLIENT','Client'),('PROVIDER','Service Provider')])
 class Meta: model=User; fields=('username','email','phone','role')
class ProviderForm(forms.ModelForm):
 class Meta: model=ProviderProfile; fields=('bio','base_location','service_radius_km','id_document','selfie')
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  for field in ('bio','base_location','id_document','selfie'): self.fields[field].required=True
class ServiceForm(forms.ModelForm):
 class Meta: model=Service; fields=('category','title','description','is_active')
class PackageForm(forms.ModelForm):
 class Meta: model=Package; fields=('tier','name','price','duration_minutes','description')
class BookingForm(forms.Form):
 start_at=forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type':'datetime-local'})); address=forms.CharField(max_length=250); special_instructions=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':2})); budget_amount=forms.DecimalField(required=False,min_value=0,decimal_places=2,initial=0)
class MessageForm(forms.ModelForm):
 class Meta: model=Message; fields=('body',); widgets={'body':forms.TextInput(attrs={'placeholder':'Write a message…'})}
class ReviewForm(forms.ModelForm):
 class Meta: model=Review; fields=('stars','comment'); widgets={'stars':forms.Select(choices=[(i,f'{i} stars') for i in range(1,6)])}
class ProofForm(forms.ModelForm):
 class Meta: model=BookingProof; fields=('kind','image','caption')
class ReportForm(forms.ModelForm):
 class Meta: model=Report; fields=('details',)
class DisputeForm(forms.ModelForm):
 class Meta: model=Dispute; fields=('reason',)

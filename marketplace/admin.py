from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *
@admin.register(User)
class CustomUserAdmin(UserAdmin): fieldsets=UserAdmin.fieldsets+(('ChoreMarket',{'fields':('role','phone','is_suspended')}),)
admin.site.register([ProviderProfile,Category,Service,Package,WorkingHours,BlockedDate,Booking,Payment,BookingProof,Message,Review,Report,Dispute,Notification])

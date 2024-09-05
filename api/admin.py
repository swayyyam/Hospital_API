from django.contrib import admin
from .models import Department,PatientRecord

admin.site.register(PatientRecord)
admin.site.register(Department)

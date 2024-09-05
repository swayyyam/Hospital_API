from django.urls import path
from .views import*
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
        path('doctors/', DoctorListView.as_view(), name='doctors'),
        path('doctors/<int:pk>/', doctor_detail, name='doctor_detail'),
        path('patients/', PatientListView.as_view(), name='patients'),
        path('patients/<int:pk>/', patient_detail, name='patient_detail'),
        path('patient_records/', PatientRecordListView.as_view(), name='patient_records'),
        path('patient_records/<int:pk>/', patient_record_detail, name='patient_record_detail'),
        path('departments/', DepartmentListView.as_view(), name='departments'),
        path('department/<int:pk>/doctors/', DepartmentDoctorsView.as_view(), name='department_doctors'),
        path('department/<int:pk>/patients/', DepartmentPatientsView.as_view(), name='department_patients'),
        path('login/', obtain_auth_token, name='login'),
        path('register/', register, name='register'),
        path('logout/', logout_view, name='logout'),
]
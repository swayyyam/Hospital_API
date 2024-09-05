from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import Group
from .models import Department, PatientRecord
from .serializers import DepartmentSerializer, PatientRecordSerializer
from rest_framework.decorators import api_view, permission_classes
from oauth2_provider.models import AccessToken
from django.utils import timezone
from rest_framework.permissions import BasePermission


class CanViewOwnRecords(BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('api.fetch_records')

class CanViewModifyDepartmentRecords(BasePermission):
    def has_permission(self, request, view):
        return (request.user.groups.filter(name='Doctors').exists() and
                (request.user.has_perm('api.fetch_own_patients_records') or
                 request.user.has_perm('api.modify_own_patients_records')))


class DoctorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.groups.filter(name='Doctors').exists():
            doctors = User.objects.filter(groups__name='Doctors').values('id', 'username')
            return Response(doctors, status=status.HTTP_200_OK)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

    def post(self, request):
        if request.user.groups.filter(name='Doctors').exists():
            return Response({"detail": "Doctor added"}, status=status.HTTP_201_CREATED)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def doctor_detail(request, pk):
    try:
        doctor = User.objects.get(pk=pk, groups__name='Doctors')
    except User.DoesNotExist:
        return Response({"detail": "Doctor not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.user != doctor:
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        return Response({"id": doctor.id, "username": doctor.username}, status=status.HTTP_200_OK)

    if request.method == 'PUT':
        return Response({"detail": "Doctor updated"}, status=status.HTTP_200_OK)

    if request.method == 'DELETE':
        return Response({"detail": "Doctor deleted"}, status=status.HTTP_204_NO_CONTENT)

class PatientListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.groups.filter(name='Doctors').exists():
            patients = User.objects.filter(groups__name='Patients').values('id', 'username')
            return Response(patients, status=status.HTTP_200_OK)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

    def post(self, request):
        if request.user.groups.filter(name='Doctors').exists():
            return Response({"detail": "Patient added"}, status=status.HTTP_201_CREATED)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def patient_detail(request, pk):
    try:
        patient = User.objects.get(pk=pk, groups__name='Patients')
    except User.DoesNotExist:
        return Response({"detail": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.user != patient and not request.user.groups.filter(name='Doctors').exists():
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        return Response({"id": patient.id, "username": patient.username}, status=status.HTTP_200_OK)

    if request.method == 'PUT':
        return Response({"detail": "Patient updated"}, status=status.HTTP_200_OK)

    if request.method == 'DELETE':
        return Response({"detail": "Patient deleted"}, status=status.HTTP_204_NO_CONTENT)

class PatientRecordListView(APIView):
    permission_classes = [IsAuthenticated, CanViewOwnRecords | CanViewModifyDepartmentRecords]

    def get(self, request):
        if request.user.groups.filter(name='Doctors').exists():
            # If user is a doctor, fetch records for patients in their department
            records = PatientRecord.objects.filter(department__in=request.user.department_set.all())
        else:
            # If user is a patient, fetch only their own records
            records = PatientRecord.objects.filter(patient=request.user)
        
        return Response(records.values(), status=status.HTTP_200_OK)

    def post(self, request):
        # Only allow doctors to create records
        if request.user.groups.filter(name='Doctors').exists():
            # Create patient record logic goes here
            return Response({"detail": "Patient record created"}, status=status.HTTP_201_CREATED)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, CanViewOwnRecords | CanViewModifyDepartmentRecords])
def patient_record_detail(request, pk):
    try:
        record = PatientRecord.objects.get(pk=pk)
    except PatientRecord.DoesNotExist:
        return Response({"detail": "Record not found"}, status=status.HTTP_404_NOT_FOUND)

    # Patients can only see their own records
    if request.user == record.patient:
        if request.method == 'GET':
            return Response({
                'record_id': record.record_id,
                'patient': record.patient.username,
                'diagnostics': record.diagnostics,
                'observations': record.observations,
                'treatments': record.treatments,
                'department': record.department.name,
                'created_date': record.created_date
            }, status=status.HTTP_200_OK)

    # Doctors can view and modify records of patients in their department
    elif request.user.groups.filter(name='Doctors').exists():
        if record.department in request.user.department_set.all():
            if request.method == 'GET':
                return Response({
                    'record_id': record.record_id,
                    'patient': record.patient.username,
                    'diagnostics': record.diagnostics,
                    'observations': record.observations,
                    'treatments': record.treatments,
                    'department': record.department.name,
                    'created_date': record.created_date
                }, status=status.HTTP_200_OK)

            if request.method == 'PUT':
                # Modify record logic goes here (e.g., update diagnostics, observations, etc.)
                record.diagnostics = request.data.get('diagnostics', record.diagnostics)
                record.observations = request.data.get('observations', record.observations)
                record.treatments = request.data.get('treatments', record.treatments)
                record.save()
                return Response({"detail": "Record updated"}, status=status.HTTP_200_OK)

            if request.method == 'DELETE':
                record.delete()
                return Response({"detail": "Record deleted"}, status=status.HTTP_204_NO_CONTENT)

    return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

class DepartmentListView(APIView):
    def get(self, request):
        departments = Department.objects.all()
        return Response(departments.values(), status=status.HTTP_200_OK)

    def post(self, request):
        return Response({"detail": "Department created"}, status=status.HTTP_201_CREATED)

class DepartmentDoctorsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if request.user.groups.filter(name='Doctors').exists():
            department = Department.objects.get(pk=pk)
            doctors = department.doctor_set.all().values('id', 'username')
            return Response(doctors, status=status.HTTP_200_OK)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

    def put(self, request, pk):
        if request.user.groups.filter(name='Doctors').exists():
            return Response({"detail": "Doctors updated"}, status=status.HTTP_200_OK)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

class DepartmentPatientsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if request.user.groups.filter(name='Doctors').exists():
            department = Department.objects.get(pk=pk)
            patients = department.patientrecord_set.all().values('patient__id', 'patient__username')
            return Response(patients, status=status.HTTP_200_OK)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

    def put(self, request, pk):
        if request.user.groups.filter(name='Doctors').exists():
            return Response({"detail": "Patients updated"}, status=status.HTTP_200_OK)
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    username = request.data.get('username')
    password = request.data.get('password')
    group_type = request.data.get('group')  

    if username is None or password is None or group_type is None:
        return Response({'detail': 'Please provide username, password, and group.'}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(username=username).exists():
        return Response({'detail': 'Username already taken.'}, status=status.HTTP_400_BAD_REQUEST)

   
    user = User.objects.create_user(username=username, password=password)
    
    if group_type.lower() == 'doctor':
        doctors_group = Group.objects.get(name='Doctors')
        user.groups.add(doctors_group)
    elif group_type.lower() == 'patient':
        patients_group = Group.objects.get(name='Patients')
        user.groups.add(patients_group)
    else:
        return Response({'detail': 'Invalid group. Please choose either Doctor or Patient.'}, status=status.HTTP_400_BAD_REQUEST)

    user.save()

    token, created = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'username': username, 'group': group_type}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        token = AccessToken.objects.get(user=request.user)
        token.expires = timezone.now()
        token.save()
    except AccessToken.DoesNotExist:
        pass
    
    return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


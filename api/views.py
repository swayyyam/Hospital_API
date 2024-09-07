from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User, Group
from rest_framework import status
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from .models import Department, PatientRecord
from .serializers import PatientRecordSerializer
from oauth2_provider.models import AccessToken
from django.utils import timezone
from oauth2_provider.settings import oauth2_settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
import logging

# Set up logging
logger = logging.getLogger(__name__)


class CanViewOwnRecords(BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('api.fetch_records')

class CanViewModifyDepartmentRecords(BasePermission):
    def has_permission(self, request, view):
        return (request.user.groups.filter(name='Doctors').exists() and
                (request.user.has_perm('api.fetch_own_patients_records') or
                 request.user.has_perm('api.modify_own_patients_records')))


class DoctorListView(APIView):
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.groups.filter(name='Doctors').exists():
            doctors = User.objects.filter(groups__name='Doctors').values('id', 'username')
            return Response(doctors, status=status.HTTP_200_OK)
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
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated, CanViewOwnRecords | CanViewModifyDepartmentRecords]

    def get(self, request):
        logger.info(f"Headers: {request.headers}")
        logger.info(f"User: {request.user}")
        logger.info(f"Auth: {request.auth}")

        if request.user.groups.filter(name='Doctors').exists():
            # Retrieve patient records, but only those whose patients are in the "Patients" group
            records = PatientRecord.objects.filter(department__in=request.user.department_set.all(), patient__groups__name='Patients')
            return Response(records.values(), status=status.HTTP_200_OK)
        
        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

    def post(self, request):
        if request.user.groups.filter(name='Doctors').exists():
            # Ensure the user associated with the record is in the Patients group
            patient_id = request.data.get('patient')
            try:
                patient = User.objects.get(id=patient_id, groups__name='Patients')
                # Proceed with record creation (Omitted for brevity)
                return Response({"detail": "Patient record created"}, status=status.HTTP_201_CREATED)
            except User.DoesNotExist:
                return Response({"detail": "Invalid patient. Ensure the user belongs to the Patients group."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, CanViewOwnRecords | CanViewModifyDepartmentRecords])
def patient_record_detail(request, pk):
    try:
        record = PatientRecord.objects.get(pk=pk, patient__groups__name='Patients')  # Ensure patient belongs to the Patients group
    except PatientRecord.DoesNotExist:
        return Response({"detail": "Record not found or invalid patient group."}, status=status.HTTP_404_NOT_FOUND)

    if request.user == record.patient:
        # Return record if the user is the patient
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

    # Doctors can view and modify their department's patients' records
    elif request.user.groups.filter(name='Doctors').exists() and record.department in request.user.department_set.all():
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

    if not username or not password or not group_type:
        return Response({'detail': 'Please provide username, password, and group.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'detail': 'Username already taken.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password)
    if group_type.lower() == 'doctor':
        group = Group.objects.get(name='Doctors')
    elif group_type.lower() == 'patient':
        group = Group.objects.get(name='Patients')
    else:
        return Response({'detail': 'Invalid group. Please choose either Doctor or Patient.'}, status=status.HTTP_400_BAD_REQUEST)

    user.groups.add(group)
    user.save()

    return Response({'username': username, 'group': group_type}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Log out a user by revoking their access token and marking it as expired.
    """
    # Get the token from the Authorization header
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return Response({'detail': 'No valid token provided.'}, status=status.HTTP_400_BAD_REQUEST)

    # Extract the token string
    token_str = auth_header.split(' ')[1]

    try:
        # Retrieve the access token
        token = AccessToken.objects.get(token=token_str)
        token.expires = timezone.now()  # Mark token as expired
        token.save()

        # Optionally, you could also delete or revoke the token
        oauth2_settings.ACCESS_TOKEN_MODEL.objects.filter(token=token_str).delete()

        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)

    except AccessToken.DoesNotExist:
        return Response({'detail': 'Token not found or already expired.'}, status=status.HTTP_400_BAD_REQUEST)


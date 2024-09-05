from django.contrib.auth.models import User, Group

doctors_group, created = Group.objects.get_or_create(name='Doctors')
patients_group, created = Group.objects.get_or_create(name='Patients')

doctor = User.objects.create_user(username='dr_jones', password='admin2001')
doctor.groups.add(doctors_group)

patient = User.objects.create_user(username='john_doe', password='admin2001')
patient.groups.add(patients_group)

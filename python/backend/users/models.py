from django.db import models


class University(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=500, null=True, blank=True)
    logo = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'universities'


class User(models.Model):
    ROLE_CHOICES = [('student', 'Student'), ('admin', 'Admin')]
    STATUS_CHOICES = [('active', 'Active'), ('blocked', 'Blocked')]

    id = models.AutoField(primary_key=True)
    university = models.ForeignKey(
        University, db_column='university_id', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='users',
    )
    name = models.CharField(max_length=150)
    email = models.CharField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    avatar = models.CharField(max_length=500, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    role = models.CharField(max_length=7, choices=ROLE_CHOICES, default='student')
    is_verified = models.BooleanField(default=False)
    status = models.CharField(max_length=7, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    class Meta:
        managed = False
        db_table = 'users'


class Subject(models.Model):
    id = models.AutoField(primary_key=True)
    university = models.ForeignKey(
        University, db_column='university_id', on_delete=models.CASCADE,
        related_name='subjects',
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'subjects'

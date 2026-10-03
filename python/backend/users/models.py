from django.db import models


class University(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=500, null=True, blank=True)
    website = models.URLField(max_length=2048, null=True, blank=True)
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'universities'


class Faculty(models.Model):
    university = models.ForeignKey(
        University, db_column='university_id', on_delete=models.DO_NOTHING,
        related_name='faculties',
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'faculties'
        unique_together = [('university', 'code')]


class Major(models.Model):
    faculty = models.ForeignKey(
        Faculty, db_column='faculty_id', on_delete=models.DO_NOTHING,
        related_name='majors',
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'majors'
        unique_together = [('faculty', 'code')]


class User(models.Model):
    ROLE_CHOICES = [('STUDENT', 'Student'), ('ADMIN', 'Admin')]
    STATUS_CHOICES = [
        ('PENDING_VERIFICATION', 'Pending verification'),
        ('ACTIVE', 'Active'),
        ('BLOCKED', 'Blocked'),
    ]

    email = models.EmailField(max_length=254, unique=True)
    password_hash = models.CharField(max_length=255)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, null=True, blank=True)
    avatar_url = models.CharField(max_length=2048, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    university = models.ForeignKey(
        University, db_column='university_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='users',
    )
    faculty = models.ForeignKey(
        Faculty, db_column='faculty_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='users',
    )
    major = models.ForeignKey(
        Major, db_column='major_id', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='users',
    )
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    @property
    def name(self):
        return self.full_name

    @property
    def avatar(self):
        return self.avatar_url

    @property
    def is_verified(self):
        return self.status == 'ACTIVE'

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    class Meta:
        managed = False
        db_table = 'users'


class OtpVerification(models.Model):
    CHANNEL_CHOICES = [('EMAIL', 'Email'), ('PHONE', 'Phone')]
    PURPOSE_CHOICES = [
        ('REGISTER', 'Register'),
        ('LOGIN', 'Login'),
        ('FORGOT_PASSWORD', 'Forgot password'),
        ('CHANGE_EMAIL', 'Change email'),
        ('CHANGE_PHONE', 'Change phone'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('EXPIRED', 'Expired'),
        ('BLOCKED', 'Blocked'),
    ]

    user = models.ForeignKey(
        User,
        db_column='user_id',
        null=True,
        blank=True,
        db_index=False,
        on_delete=models.SET_NULL,
        related_name='otp_verifications',
    )
    channel = models.CharField(max_length=5, choices=CHANNEL_CHOICES)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    target = models.CharField(max_length=255)
    otp_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    resend_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=8,
        choices=STATUS_CHOICES,
        default='PENDING',
    )
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'otp_verifications'
        indexes = [
            models.Index(
                fields=['target', 'purpose', 'status'],
                name='idx_otp_target_purpose_status',
            ),
            models.Index(
                fields=['user', 'purpose', 'status'],
                name='idx_otp_user_purpose_status',
            ),
            models.Index(fields=['expires_at'], name='idx_otp_expires_at'),
        ]


class UserAddress(models.Model):
    user = models.ForeignKey(
        User, db_column='user_id', on_delete=models.DO_NOTHING,
        related_name='addresses',
    )
    recipient_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    address_line = models.CharField(max_length=500)
    ward = models.CharField(max_length=150)
    district = models.CharField(max_length=150)
    city = models.CharField(max_length=150)
    postal_code = models.CharField(max_length=30, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'user_addresses'


class UserViolation(models.Model):
    user = models.ForeignKey(
        User, db_column='user_id', on_delete=models.DO_NOTHING,
        related_name='violations',
    )
    violation_type = models.CharField(max_length=50)
    reason = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    severity = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default='OPEN')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, db_column='created_by', null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name='created_violations',
    )
    created_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'user_violations'


class Subject(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    credits = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'subjects'


class Language(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, default='ACTIVE')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'languages'

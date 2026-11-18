from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, email, name, role='donor', password=None, **extra_fields):
        if not email:
            raise ValueError('Users must provide an email address.')
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        # Donors are approved by default; NGOs and Institutions require admin verification
        if role == 'donor':
            user.verification_status = 'approved'
        elif role in ('ngo_volunteer', 'institution'):
            user.verification_status = extra_fields.get('verification_status', 'pending')
        elif role == 'admin':
            user.verification_status = 'approved'
            
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name='Administrator', password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('verification_status', 'approved')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, name, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_DONOR = 'donor'
    ROLE_NGO = 'ngo_volunteer'
    ROLE_INSTITUTION = 'institution'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = (
        (ROLE_DONOR, 'Donor (Hotel, Restaurant, Hostel, Household)'),
        (ROLE_NGO, 'NGO / Volunteer'),
        (ROLE_INSTITUTION, 'Beneficiary Institution (Orphanage, Shelter, Old-Age Home)'),
        (ROLE_ADMIN, 'Administrator'),
    )

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    VERIFICATION_CHOICES = (
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    )

    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, help_text="Full name or organization name")
    email = models.EmailField(unique=True, max_length=254)
    phone = models.CharField(max_length=20, blank=True, help_text="Contact phone number")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_DONOR)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default=STATUS_PENDING)
    address = models.TextField(blank=True, help_text="Physical address")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Standard Django administrative flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()}) - {self.email}"

    @property
    def is_donor(self):
        return self.role == self.ROLE_DONOR

    @property
    def is_ngo(self):
        return self.role == self.ROLE_NGO

    @property
    def is_institution(self):
        return self.role == self.ROLE_INSTITUTION

    @property
    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def is_approved(self):
        return self.verification_status == self.STATUS_APPROVED

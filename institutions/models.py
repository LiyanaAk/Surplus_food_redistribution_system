from django.db import models
from django.conf import settings

class Institution(models.Model):
    INSTITUTION_TYPES = (
        ('orphanage', 'Orphanage'),
        ('shelter_home', 'Shelter Home'),
        ('old_age_home', 'Old-Age Home'),
        ('community_kitchen', 'Community Kitchen'),
        ('rehab_center', 'Rehabilitation Center'),
        ('other', 'Other Beneficiary Organization'),
    )

    institution_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='institution_profile',
        db_column='user_id'
    )
    institution_type = models.CharField(max_length=100, choices=INSTITUTION_TYPES, default='shelter_home')
    capacity = models.PositiveIntegerField(default=50, help_text="Number of people/residents served")

    class Meta:
        db_table = 'institutions'
        verbose_name = 'Institution'
        verbose_name_plural = 'Institutions'

    def __str__(self):
        return f"{self.user.name} ({self.get_institution_type_display()} - Cap: {self.capacity})"

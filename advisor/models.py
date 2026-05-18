# advisor/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True, default="")
    company = models.CharField(max_length=120, blank=True, default="")
    role = models.CharField(max_length=80, blank=True, default="")
    cloud_provider = models.CharField(max_length=40, blank=True, default="")
    monthly_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    extra_emails = models.TextField(blank=True, default="")

    def get_email_list(self):
        if not self.extra_emails:
            return []
        return [e.strip() for e in self.extra_emails.split(",") if e.strip()]

    def __str__(self):
        return f"Profile({self.user.username})"

@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
    else:
        # ensure exists
        try:
            instance.profile
        except Profile.DoesNotExist:
            Profile.objects.create(user=instance)

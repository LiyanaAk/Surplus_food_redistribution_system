from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .forms import UserLoginForm, DonorRegistrationForm, NGORegistrationForm, InstitutionRegistrationForm, UserProfileUpdateForm
from .models import User
from institutions.models import Institution
from notifications.models import Notification

def login_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            messages.success(request, f"Welcome back, {user.name}!")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect_user_by_role(user)
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'title': 'Log In'})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out safely.")
    return redirect('core:home')


def register_select_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)
    return render(request, 'accounts/register_select.html', {'title': 'Register Role Selection'})


def register_donor_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == 'POST':
        form = DonorRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.role = User.ROLE_DONOR
                user.verification_status = User.STATUS_APPROVED
                user.set_password(form.cleaned_data['password'])
                user.save()

                Notification.objects.create(
                    user=user,
                    message=f"Welcome {user.name}! Your donor account is active. You can now post surplus food listings."
                )

                login(request, user)
                messages.success(request, "Registration successful! Welcome to the Surplus Food Redistribution System.")
                return redirect('listings:donor_dashboard')
    else:
        form = DonorRegistrationForm()

    return render(request, 'accounts/register_donor.html', {'form': form, 'title': 'Register as Food Donor'})


def register_ngo_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == 'POST':
        form = NGORegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.role = User.ROLE_NGO
                user.verification_status = User.STATUS_PENDING
                user.set_password(form.cleaned_data['password'])
                user.save()

                # Notify Admins
                admin_users = User.objects.filter(role=User.ROLE_ADMIN)
                for admin in admin_users:
                    Notification.objects.create(
                        user=admin,
                        message=f"New NGO registration pending approval: '{user.name}' ({user.email})."
                    )

                messages.success(
                    request,
                    "Registration submitted! In accordance with food redistribution security protocols, "
                    "your NGO account must be verified by an administrator before claiming food. You will be notified upon approval."
                )
                return redirect('accounts:login')
    else:
        form = NGORegistrationForm()

    return render(request, 'accounts/register_ngo.html', {'form': form, 'title': 'Register as NGO / Volunteer'})


def register_institution_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == 'POST':
        form = InstitutionRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.role = User.ROLE_INSTITUTION
                user.verification_status = User.STATUS_PENDING
                user.set_password(form.cleaned_data['password'])
                user.save()

                Institution.objects.create(
                    user=user,
                    institution_type=form.cleaned_data['institution_type'],
                    capacity=form.cleaned_data['capacity']
                )

                # Notify Admins
                admin_users = User.objects.filter(role=User.ROLE_ADMIN)
                for admin in admin_users:
                    Notification.objects.create(
                        user=admin,
                        message=f"New Beneficiary Institution pending approval: '{user.name}' (Cap: {form.cleaned_data['capacity']})."
                    )

                messages.success(
                    request,
                    "Institution registered successfully! Your account will be verified by an administrator to start receiving food routed deliveries."
                )
                return redirect('accounts:login')
    else:
        form = InstitutionRegistrationForm()

    return render(request, 'accounts/register_institution.html', {'form': form, 'title': 'Register Beneficiary Institution'})


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile details have been updated successfully.")
            return redirect('accounts:profile')
    else:
        form = UserProfileUpdateForm(instance=user)

    return render(request, 'accounts/profile.html', {'form': form, 'title': 'My Profile'})


def redirect_user_by_role(user):
    if user.is_admin_user:
        return redirect('core:admin_dashboard')
    elif user.is_ngo:
        return redirect('claims:ngo_dashboard')
    elif user.is_institution:
        return redirect('institutions:institution_dashboard')
    else:
        return redirect('listings:donor_dashboard')

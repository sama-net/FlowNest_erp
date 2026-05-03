from django.shortcuts import render, redirect
from .models import Profile, DataFile
from django.contrib.auth.decorators import login_required
from .forms import ProfileForm, DataFileForm
import threading

@login_required
def profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('file_upload')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'products/profile.html', {'form': form})

@login_required
def file_upload(request):
    if request.method == 'POST':
        source_dept = request.POST.get('source_department')
        target_dept = request.POST.get('target_department')
        uploaded_files = request.FILES.getlist('file')  # supports multiple files

        for uploaded_file in uploaded_files:
            filename = uploaded_file.name.lower()
            if filename.endswith('.pdf'):
                ftype = 'pdf'
            elif filename.endswith(('.xlsx', '.xls', '.csv')):
                ftype = 'excel' if not filename.endswith('.csv') else 'csv'
            else:
                ftype = 'other'

            df = DataFile.objects.create(
                uploaded_by=request.user,
                file=uploaded_file,
                file_type=ftype,
                source_department=source_dept,
                target_department=target_dept,
                company=getattr(request.user.profile, 'company', None)
            )

            # Auto-ingest into RAG using managed task pool
            from .services.task_manager import enqueue_task, sync_file_to_rag_task
            enqueue_task(sync_file_to_rag_task, df.pk)

        return redirect('file_upload')
    else:
        form = DataFileForm()
    
    # Show all company files visible to this user (using relational company)
    user_profile = getattr(request.user, 'profile', None)
    if not user_profile or not user_profile.company:
        files = DataFile.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    elif user_profile.role in ['owner', 'developer']:
        files = DataFile.objects.filter(company=user_profile.company).order_by('-uploaded_at')
    elif user_profile.role == 'manager':
        files = DataFile.objects.filter(
            company=user_profile.company,
            source_department=user_profile.department
        ).order_by('-uploaded_at')
    else:
        files = DataFile.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    
    return render(request, 'products/file_upload.html', {'form': form, 'files': files})
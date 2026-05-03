from django import forms
from .models import Profile, DataFile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['department', 'role', 'company_name', 'company_description', 'industry']

class DataFileForm(forms.ModelForm):
    class Meta:
        model = DataFile
        fields = ['file', 'source_department', 'target_department']
        labels = {
            'file': 'الملف (PDF, Excel)',
            'source_department': 'الإدارة المصدرة (إدارتك)',
            'target_department': 'إدارة الوجهة السُمح لها بالاطلاع',
        }
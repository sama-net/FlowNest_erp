from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Company(models.Model):
    name = models.CharField(max_length=200, unique=True)
    industry = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CustomDepartment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments', null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=200, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    template_slug = models.CharField(max_length=50, default='general')
    active_modules = models.JSONField(default=dict, blank=True)
    custom_schema = models.JSONField(default=list, blank=True) # [{"name":"price", "type":"number", "label":"السعر"}]
    ui_settings = models.JSONField(default=dict, blank=True) # {"color": "#4f46e5", "icon": "fa-box"}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company_name', 'name')

    def __str__(self):
        return f"{self.name} ({self.company_name})"

class Project(models.Model):
    STATUS_CHOICES = [('active', 'نشط'), ('completed', 'مكتمل'), ('on_hold', 'متوقف مؤقتاً')]
    name = models.CharField(max_length=200) # e.g. Villa 101
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='projects', null=True, blank=True)
    location = models.CharField(max_length=500)
    google_maps_link = models.URLField(blank=True)
    estimated_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    forecasted_completion_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    company_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.company_name}"

    @property
    def total_actual_costs(self):
        return self.files.aggregate(total=models.Sum('linked_cost'))['total'] or 0

class Profile(models.Model):
    ROLE_CHOICES = [
        ('developer', 'المطور / Super Admin'),
        ('owner', 'مالك/CEO'),
        ('manager', 'مدير إدارة'),
        ('engineer', 'طاقم عمل / مهندس'),
    ]
    PLAN_CHOICES = [
        ('free', 'مجاني (فترة تجريبية)'),
        ('1_month', 'شهر (8000 ج.م)'),
        ('3_months', 'ثلاثة أشهر (23000 ج.م)'),
        ('1_year', 'سنة (90000 ج.م)')
    ]
    SECTOR_CHOICES = [
        ('corporate', 'شركات / تجاري'),
        ('education', 'تعليمي / مدارس / جامعات'),
        ('medical', 'طبي / مستشفيات / عيادات'),
        ('construction', 'إنشاءات / عقارات (Villas)'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='profiles', null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=200, default="My Company", db_index=True)
    department = models.ForeignKey(CustomDepartment, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='engineer', db_index=True)
    sector = models.CharField(max_length=50, choices=SECTOR_CHOICES, default='corporate')
    plan = models.CharField(max_length=50, choices=PLAN_CHOICES, default='free')
    is_approved = models.BooleanField(default=False, db_index=True)
    is_locked = models.BooleanField(default=False)
    company_description = models.TextField(blank=True, null=True)
    industry = models.CharField(max_length=200, blank=True, null=True)
    full_name = models.CharField(max_length=200, blank=True, null=True)
    is_primary_owner = models.BooleanField(default=False)
    is_platform_admin = models.BooleanField(default=False)

    def __str__(self):
        dept_name = self.department.name if self.department else "No Dept"
        return f"{self.user.username} ({self.get_role_display()}) - {self.company_name} [{dept_name}]"

class DataFile(models.Model):
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='company_files/')
    file_type = models.CharField(max_length=20)
    source_department = models.CharField(max_length=100) # Flexible string
    target_department = models.CharField(max_length=100) # Flexible string
    department = models.ForeignKey(CustomDepartment, on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    linked_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='files', null=True, blank=True, db_index=True)
    
    # NEW: Optimization & Status Tracking
    analysis_result = models.JSONField(null=True, blank=True)
    is_synced = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.file.name} (من {self.source_department})"


class FinancialRecord(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='financial_records', null=True, blank=True)
    company_name = models.CharField(max_length=200)
    date = models.DateField()
    revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    expenses = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cogs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    taxes = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    related_file = models.ForeignKey('DataFile', on_delete=models.SET_NULL, null=True, blank=True, related_name='financial_records')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"{self.company_name} - {self.date}: Profit {self.net_profit}"

    def save(self, *args, **kwargs):
        self.net_profit = (self.revenue or 0) - (self.expenses or 0) - (self.cogs or 0) - (self.taxes or 0)
        super().save(*args, **kwargs)

class FinancialAlert(models.Model):
    STATUS_CHOICES = [('danger', 'خطر'), ('warning', 'تحذير'), ('safe', 'آمن')]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='alerts')
    message = models.TextField()
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='warning')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alert for {self.project.name}: {self.status}"

class CompanyEconomics(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='economics', null=True, blank=True)
    company_name = models.CharField(max_length=200, db_index=True)
    total_shares = models.BigIntegerField(default=1000000)
    share_price = models.DecimalField(max_digits=12, decimal_places=2, default=1.0)
    assets_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    liabilities_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    market_cap = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    industry_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} - Val: {self.market_cap}"

    def calculate_valuation(self, net_profit_annual):
        """Logic: (Assets - Liabilities) + (Net Profit * Industry Multiplier)"""
        equity_value = self.assets_value - self.liabilities_value
        company_value = equity_value + (net_profit_annual * self.industry_multiplier)
        self.market_cap = company_value
        if self.total_shares > 0:
            self.share_price = company_value / self.total_shares
        self.save()
        return company_value

    def save(self, *args, **kwargs):
        if not self.market_cap:
            self.market_cap = self.total_shares * self.share_price
        super().save(*args, **kwargs)


# -------------------------------------------------------
#  HR DEPARTMENT MODELS
# -------------------------------------------------------

class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('annual', 'إجازة سنوية'), ('sick', 'إجازة مرضية'),
        ('unpaid', 'إجازة بدون راتب'), ('emergency', 'إجازة طارئة'),
        ('maternity', 'إجازة وضع'),
    ]
    STATUS_CHOICES = [('pending','معلق'), ('approved','مقبول'), ('rejected','مرفوض')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='leave_requests')
    employee = models.ForeignKey('Profile', on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, default='annual')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    manager_approved = models.BooleanField(default=False)
    hr_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def days_count(self):
        return (self.end_date - self.start_date).days + 1

    def __str__(self):
        return f"{self.employee.user.username} - {self.get_leave_type_display()}"


class EmployeeSalary(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='salaries')
    employee = models.ForeignKey('Profile', on_delete=models.CASCADE, related_name='salaries')
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonuses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'month', 'year')

    def save(self, *args, **kwargs):
        self.net_salary = self.base_salary + self.bonuses - self.deductions
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.user.username} - {self.month}/{self.year}"


# -------------------------------------------------------
#  IT DEPARTMENT MODELS
# -------------------------------------------------------

class SupportTicket(models.Model):
    PRIORITY_CHOICES = [('low','منخفضة'), ('medium','متوسطة'), ('high','عالية'), ('critical','حرجة')]
    STATUS_CHOICES = [('open','مفتوحة'), ('in_progress','قيد التنفيذ'), ('resolved','تم الحل'), ('closed','مغلقة')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tickets')
    department = models.ForeignKey(CustomDepartment, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tickets')
    assigned_to = models.ForeignKey('Profile', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title}"


# -------------------------------------------------------
#  SALES DEPARTMENT MODELS
# -------------------------------------------------------

class SalesDeal(models.Model):
    STAGE_CHOICES = [
        ('lead', 'عميل محتمل'), ('qualified', 'مؤهل'),
        ('proposal', 'عرض سعر'), ('negotiation', 'تفاوض'),
        ('won', 'صفقة ناجحة'), ('lost', 'صفقة خاسرة'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='deals')
    client_name = models.CharField(max_length=200)
    client_contact = models.CharField(max_length=200, blank=True)
    deal_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='lead')
    probability = models.PositiveSmallIntegerField(default=50)
    assigned_to = models.ForeignKey('Profile', on_delete=models.SET_NULL, null=True, blank=True, related_name='deals')
    expected_close_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client_name} - {self.get_stage_display()}"


# -------------------------------------------------------
#  MARKETING DEPARTMENT MODELS
# -------------------------------------------------------

class MarketingCampaign(models.Model):
    STATUS_CHOICES = [('planned','مخططة'), ('active','نشطة'), ('paused','متوقفة'), ('completed','مكتملة')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_spend = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    leads_generated = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='campaigns')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def roi(self):
        if self.actual_spend > 0:
            return round(((self.conversions * 1000 - float(self.actual_spend)) / float(self.actual_spend)) * 100, 1)
        return 0

    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"


# -------------------------------------------------------
#  PROCUREMENT DEPARTMENT MODELS
# -------------------------------------------------------

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [('pending','معلق'), ('approved','تمت الموافقة'), ('received','تم الاستلام'), ('cancelled','ملغي')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='purchase_orders')
    vendor_name = models.CharField(max_length=200)
    item_description = models.TextField()
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    manager_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='manager_approved_pos')
    finance_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_approved_pos')
    ordered_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchase_orders')
    order_date = models.DateField(auto_now_add=True)
    delivery_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.vendor_name} - {self.item_description[:50]}"


# -------------------------------------------------------
#  LEGAL DEPARTMENT MODELS
# -------------------------------------------------------

class LegalContract(models.Model):
    CONTRACT_TYPES = [
        ('service','عقد خدمة'), ('employment','عقد عمل'),
        ('nda','اتفاقية سرية'), ('partnership','عقد شراكة'),
        ('supplier','عقد توريد'), ('lease','عقد إيجار'),
    ]
    STATUS_CHOICES = [('draft','مسودة'), ('active','نشط'), ('expired','منتهي'), ('terminated','ملغي')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contracts')
    title = models.CharField(max_length=200)
    party_name = models.CharField(max_length=200)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES, default='service')
    value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    file = models.FileField(upload_to='contracts/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contracts')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_expiring_soon(self):
        from django.utils import timezone
        if self.end_date:
            return 0 <= (self.end_date - timezone.now().date()).days <= 30
        return False

    def __str__(self):
        return f"{self.title} - {self.party_name}"

# -------------------------------------------------------
#  EDUCATION DEPARTMENT MODELS
# -------------------------------------------------------

class StudentEnrollment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='students')
    student_name = models.CharField(max_length=200)
    grade_level = models.CharField(max_length=100)
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=[('active','نشط'), ('graduated','خريج'), ('transferred','منقول')], default='active')
    gpa = models.DecimalField(max_digits=4, decimal_places=2, default=0.0)
    grades = models.TextField(blank=True, null=True, help_text="سجل الدرجات")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student_name} - {self.grade_level}"

class Course(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='courses')
    course_name = models.CharField(max_length=200)
    instructor = models.ForeignKey('Profile', on_delete=models.SET_NULL, null=True, blank=True)
    credits = models.PositiveIntegerField(default=3)
    semester = models.CharField(max_length=50)
    
    def __str__(self):
        return self.course_name

# -------------------------------------------------------
#  MEDICAL DEPARTMENT MODELS
# -------------------------------------------------------

class PatientRecord(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='patients')
    patient_name = models.CharField(max_length=200)
    age = models.PositiveIntegerField()
    diagnosis = models.TextField()
    treatment_plan = models.TextField()
    admission_date = models.DateField(auto_now_add=True)
    discharge_date = models.DateField(null=True, blank=True)
    doctor = models.ForeignKey('Profile', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return self.patient_name

class MedicalInventory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='medical_inventory')
    item_name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, choices=[('medicine','أدوية'), ('equipment','أجهزة طبية'), ('supplies','مستلزمات')])
    quantity = models.PositiveIntegerField(default=0)
    expiry_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.item_name} ({self.quantity})"

# -------------------------------------------------------
#  CONSTRUCTION DEPARTMENT MODELS
# -------------------------------------------------------

class EquipmentLog(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='equipment')
    equipment_name = models.CharField(max_length=200)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, choices=[('working','يعمل'), ('maintenance','في الصيانة'), ('broken','معطل')], default='working')
    last_maintenance = models.DateField(null=True, blank=True)
    operator = models.ForeignKey('Profile', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.equipment_name} - {self.get_status_display()}"

# -------------------------------------------------------
#  ADVANCED SCHOOL ATTENDANCE MODELS (STUDENT & FACULTY AFFAIRS)
# -------------------------------------------------------

class DailyAttendance(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='daily_attendance')
    student = models.ForeignKey(StudentEnrollment, on_delete=models.CASCADE, related_name='daily_attendance')
    date = models.DateField(default=timezone.now)
    is_present = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('student', 'date')

    def __str__(self):
        return str(self.student.student_name) + ' - ' + str(self.date)

class CourseSession(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='course_sessions')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    teacher = models.ForeignKey('Profile', on_delete=models.CASCADE, related_name='taught_sessions')
    date = models.DateField(default=timezone.now)
    session_number = models.PositiveIntegerField()
    
    def __str__(self):
        return 'Session ' + str(self.session_number) + ' - ' + str(self.course.course_name)

class SessionAttendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'حاضر'),
        ('absent', 'غائب'),
        ('escaped', 'هروب')
    ]
    session = models.ForeignKey(CourseSession, on_delete=models.CASCADE, related_name='attendance_records')
    student = models.ForeignKey(StudentEnrollment, on_delete=models.CASCADE, related_name='session_attendance')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'student')

    def __str__(self):
        return str(self.student.student_name) + ' - ' + str(self.session)

class TeacherTask(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='teacher_tasks')
    teacher = models.ForeignKey('Profile', on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(default=timezone.now)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.title) + ' - ' + str(self.teacher.user.username)

class DepartmentRecord(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='dept_records')
    department = models.ForeignKey(CustomDepartment, on_delete=models.CASCADE, related_name='records')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    dynamic_data = models.JSONField(default=dict, blank=True) # Stores the values for custom_schema fields
    ai_insight = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.title} ({self.department.name})"

# -------------------------------------------------------
#  SYSTEM & AUDIT LOG MODELS
# -------------------------------------------------------

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'إنشاء'),
        ('update', 'تعديل'),
        ('delete', 'حذف'),
        ('approve', 'موافقة'),
        ('reject', 'رفض'),
        ('login', 'تسجيل دخول'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='activity_logs')
    department = models.ForeignKey(CustomDepartment, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100) # e.g. "LeaveRequest"
    object_id = models.CharField(max_length=50) 
    description = models.TextField() # Arabic description of what happened
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.get_action_type_display()} - {self.model_name}"


from products.models import FinancialAlert, CustomDepartment

def global_sidebar_context(request):
    if not request.user.is_authenticated:
        return {}
    
    # Mapping for Arabic names and Icons
    DEPT_MAP = {
        'HR': {'ar': 'الموارد البشرية', 'icon': 'fas fa-users-cog'},
        'Finance': {'ar': 'الإدارة المالية', 'icon': 'fas fa-wallet'},
        'IT': {'ar': 'تكنولوجيا المعلومات', 'icon': 'fas fa-laptop-code'},
        'Marketing': {'ar': 'التسويق والمبيعات', 'icon': 'fas fa-ad'},
        'Operations': {'ar': 'العمليات والإنتاج', 'icon': 'fas fa-cogs'},
        'Legal': {'ar': 'الشؤون القانونية', 'icon': 'fas fa-balance-scale'},
        'Procurement': {'ar': 'المشتريات والتموين', 'icon': 'fas fa-shopping-cart'},
        'Student Affairs': {'ar': 'شؤون الطلاب', 'icon': 'fas fa-user-graduate'},
        'Faculty Affairs': {'ar': 'شؤون أعضاء التدريس', 'icon': 'fas fa-chalkboard-teacher'},
        'Academic Registry': {'ar': 'السجل الأكاديمي', 'icon': 'fas fa-id-card'},
        'Research': {'ar': 'البحث العلمي', 'icon': 'fas fa-microscope'},
        'Library': {'ar': 'المكتبة الرقمية', 'icon': 'fas fa-book-reader'},
        'Clinical': {'ar': 'العيادات الخارجيه', 'icon': 'fas fa-stethoscope'},
        'Nursing': {'ar': 'طاقم التمريض', 'icon': 'fas fa-user-nurse'},
        'Pharmacy': {'ar': 'الصيدلية والمعمل', 'icon': 'fas fa-pills'},
        'Radiology': {'ar': 'الأشعة والتصوير', 'icon': 'fas fa-x-ray'},
        'Insurance': {'ar': 'التأمين الطبي', 'icon': 'fas fa-file-medical'},
        'Project Mgmt': {'ar': 'إدارة المشروعات', 'icon': 'fas fa-project-diagram'},
        'Architecture': {'ar': 'الهندسة المعمارية', 'icon': 'fas fa-drafting-table'},
        'Engineering': {'ar': 'المكتب الفني', 'icon': 'fas fa-hard-hat'},
        'Site Ops': {'ar': 'عمليات الموقع', 'icon': 'fas fa-tools'},
        'Sales': {'ar': 'المبيعات والتعاقدات', 'icon': 'fas fa-handshake'},
    }

    try:
        profile = request.user.profile
        # Fetch active alerts for the company (RESCRICTED TO FINANCE/OWNER)
        active_alerts = []
        # Robust check for Finance access - allow all staff in Finance to see the strategic analysis button
        is_finance_managed = False
        if profile.department:
            dept_name_lower = profile.department.name.lower()
            is_finance_managed = 'finance' in dept_name_lower or 'مالية' in dept_name_lower or 'مالي' in dept_name_lower
        
        # New check for visibility: Owner OR anyone in Finance (all roles)
        is_finance_access = profile.role == 'owner' or is_finance_managed
        
        if is_finance_access:
            # Use company FK if available, else fallback to string for migration safety
            try:
                if profile.company:
                    active_alerts = FinancialAlert.objects.filter(
                        project__company=profile.company
                    ).order_by('-created_at')[:5]
                else:
                    active_alerts = FinancialAlert.objects.filter(
                        project__company_name=profile.company_name
                    ).order_by('-created_at')[:5]
            except Exception:
                active_alerts = FinancialAlert.objects.filter(
                    project__company_name=profile.company_name
                ).order_by('-created_at')[:5]
        
        # Helper to enrich department data
        def enrich_dept(dept):
            info = DEPT_MAP.get(dept.name, {'ar': dept.name, 'icon': 'fas fa-comments'})
            return {
                'id': dept.id,
                'name': dept.name,
                'ar_name': info['ar'],
                'icon': info['icon'],
                'url_name': dept.name.lower()
            }

        # Fetch departments for the company (for owners to see all)
        company_depts = []
        if profile.role == 'owner':
            raw_depts = CustomDepartment.objects.filter(company=profile.company)
            company_depts = [enrich_dept(d) for d in raw_depts]
        
        user_dept = None
        if profile.department:
            user_dept = enrich_dept(profile.department)
            
        # INFRASTRUCTURE STATUS
        import os
        is_persistent = os.getenv('RAILWAY_VOLUME_MOUNT_PATH') is not None or os.path.exists('/app/persistent_data')
        
        return {
            'sidebar_alerts': active_alerts,
            'sidebar_depts': company_depts,
            'enrich_user_dept': user_dept,
            'is_finance_manager': is_finance_access,
            'is_persistent': is_persistent,
            'build_version': 'v2.2-stable',
            'AI_KEY_CONFIGURED': bool(os.getenv('GOOGLE_API_KEY'))
        }
    except Exception as e:
        print(f"Sidebar context error: {e}")
        return {}

from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from .finance_services import PredictiveFinanceService

# Define custom signal for anomaly alerts
anomaly_alert_triggered = Signal()

@receiver(post_save, sender='products.DataFile')
def track_project_costs(sender, instance, created, **kwargs):
    """Updates project projections and company economics every time a file is linked."""
    if instance.project:
        from .models import Project, FinancialAlert, CompanyEconomics, FinancialRecord
        project = instance.project
        is_anomaly, excess = PredictiveFinanceService.check_anomaly(project)
        
        status, msg, loss_pct = PredictiveFinanceService.get_financial_guard_report(project)
        
        if status in ['danger', 'warning']:
            # Create a persistent alert record
            FinancialAlert.objects.create(
                project=project,
                message=msg,
                percent=loss_pct,
                status=status
            )
            
            # Send notification (Project is now correctly imported)
            anomaly_alert_triggered.send(
                sender=Project, project=project, excess=excess, guard_message=msg
            )
            
            if status == 'danger' and (excess > 50 or loss_pct > 50):
                project.status = 'on_hold'
                project.save()
        
        # Real-time Valuation Update using relational FK
        if project.company:
            economics, _ = CompanyEconomics.objects.get_or_create(company=project.company)
            last_profit = FinancialRecord.objects.filter(
                company=project.company
            ).order_by('-date').first()
            profit_val = float(last_profit.net_profit) if last_profit else 0
            economics.calculate_valuation(profit_val)
            economics.save()

@receiver(post_save, sender='products.Profile')
def initialize_company_economics(sender, instance, created, **kwargs):
    """Ensures a CompanyEconomics record exists for every approved company with sector multipliers."""
    if created and instance.role == 'owner' and instance.company:
        from .models import CompanyEconomics
        multipliers = {'corporate': 5.0, 'education': 3.0, 'medical': 8.0, 'construction': 6.5}
        mult = multipliers.get(instance.sector, 5.0)
        CompanyEconomics.objects.get_or_create(
            company=instance.company,
            defaults={
                'company_name': instance.company_name,
                'industry_multiplier': mult
            }
        )

@receiver(post_save, sender='products.FinancialRecord')
def auto_sync_financial_record_to_rag(sender, instance, created, **kwargs):
    """Automatically sync financial records to RAG system when updated."""
    try:
        from rag.views import _get_rag
        rag_sys = _get_rag()
        if rag_sys:
            rag_sys.sync_financial_record(instance)
    except Exception as e:
        print(f"Error auto-syncing financial record to RAG: {e}")

@receiver(post_save, sender='products.CompanyEconomics')
def auto_sync_economics_to_rag(sender, instance, created, **kwargs):
    """Automatically sync company economics to RAG system when updated."""
    try:
        from rag.views import _get_rag
        rag_sys = _get_rag()
        if rag_sys:
            rag_sys.sync_company_economics(instance)
    except Exception as e:
        print(f"Error auto-syncing company economics to RAG: {e}")

from django.db.models.signals import post_delete
from .models import LeaveRequest, PurchaseOrder, ActivityLog

def _create_activity_log(sender, instance, action, **kwargs):
    if not hasattr(instance, 'company') or not instance.company:
        return
    
    # Try to infer user
    user = None
    if hasattr(instance, 'employee') and hasattr(instance.employee, 'user'):
        user = instance.employee.user
    elif hasattr(instance, 'ordered_by'):
        user = instance.ordered_by
    elif hasattr(instance, 'created_by'):
        user = instance.created_by
        
    model_name = sender.__name__
    desc = f"تم {action} السجل ({model_name}) بمعرف {instance.pk}"
    
    # Optional context mapping
    if model_name == 'LeaveRequest':
        desc = f"تم {action} طلب إجازة للموظف {instance.employee.user.username if user else 'غير معروف'} نوع {instance.get_leave_type_display()}"
    elif model_name == 'PurchaseOrder':
        desc = f"تم {action} أمر شراء للمورد {instance.vendor_name} بقيمة {instance.total_amount}"

    ActivityLog.objects.create(
        company=instance.company,
        user=user,
        action_type='create' if action == 'إنشاء' else 'update' if action == 'تعديل' else 'delete',
        model_name=model_name,
        object_id=str(instance.pk),
        description=desc
    )

@receiver(post_save, sender=LeaveRequest)
@receiver(post_save, sender=PurchaseOrder)
def log_creation_and_updates(sender, instance, created, **kwargs):
    action = 'إنشاء' if created else 'تعديل'
    _create_activity_log(sender, instance, action, **kwargs)

@receiver(post_delete, sender=LeaveRequest)
@receiver(post_delete, sender=PurchaseOrder)
def log_deletions(sender, instance, **kwargs):
    _create_activity_log(sender, instance, 'حذف', **kwargs)


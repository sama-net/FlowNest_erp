import numpy as np
from django.utils import timezone
from .models import Project, DataFile, CompanyEconomics
from groq import Groq
from django.conf import settings as dj_settings

class PredictiveFinanceService:
    @staticmethod
    def calculate_burn_rate(project):
        """Calculates the average spending per day for a project."""
        actual_costs = project.total_actual_costs
        if actual_costs == 0:
            return 0
        
        days_active = (timezone.now() - project.created_at).days or 1
        return actual_costs / days_active

    @staticmethod
    def check_anomaly(project):
        """Triggers an alert if actual costs exceed estimation by 15%."""
        if project.estimated_budget == 0:
            return False, 0
        
        actual = project.total_actual_costs
        threshold = float(project.estimated_budget) * 1.15
        
        is_anomaly = float(actual) > threshold
        excess_percent = ((float(actual) - float(project.estimated_budget)) / float(project.estimated_budget)) * 100
        return is_anomaly, round(excess_percent, 2)

    @staticmethod
    def forecast_valuation(project):
        """
        Sophisticated Real-Estate Valuation:
        Expected Valuation = Forecasted Completion Value - (Remaining Estimated Costs * Margin)
        """
        actual = float(project.total_actual_costs)
        base_budget = float(project.estimated_budget)
        completion_value = float(project.forecasted_completion_value)
        
        if base_budget == 0: return completion_value
        
        # Calculate progress ratio
        progress = min(actual / base_budget, 1.0)
        remaining_budget = max(base_budget - actual, 0)
        
        # Risk-adjusted valuation: If spending is high/fast, valuation might be lower due to inefficiency
        burn_rate = PredictiveFinanceService.calculate_burn_rate(project)
        risk_factor = 1.0
        if burn_rate > (base_budget / 90): # Assumed 90-day cycle
            risk_factor = 0.9 # Deduct 10% for high burn risk
            
        forecasted_valuation = (completion_value - remaining_budget) * risk_factor
        return round(forecasted_valuation, 2)

    @staticmethod
    def get_financial_guard_report(project):
        """
        Calculates projected gain/loss based on current burn rate vs remaining budget.
        Returns a (status, message, percentage) tuple.
        """
        actual = float(project.total_actual_costs)
        budget = float(project.estimated_budget)
        
        if budget == 0: return "neutral", "لم يتم تحديد ميزانية تقديرية لهذا المشروع بعد.", 0
        
        burn_rate = PredictiveFinanceService.calculate_burn_rate(project)
        # Assuming 30 days remaining for projection if not specified
        projected_final = actual + (burn_rate * 30)
        
        loss_percent = ((projected_final - budget) / budget) * 100
        
        if loss_percent > 10:
            msg = f"تنبيه مصداقية: بناءً على الفواتير المرفوعة، هذا المشروع سيخسر {round(loss_percent, 1)}% لو كملنا بنفس المعدل."
            return "danger", msg, round(loss_percent, 1)
        elif loss_percent > 0:
            return "warning", "المشروع يقترب من تجاوز الميزانية. يرجى مراجعة المصروفات.", round(loss_percent, 1)
        
        return "safe", "المشروع يسير بمعدل إنفاق آمن وضمن الميزانية.", 0

    @staticmethod
    def get_ai_insight(project):
        """Uses advanced LLM reasoning to provide financial strategy for construction projects."""
        try:
            client = Groq(api_key=dj_settings.GROQ_API_KEY)
            actual = project.total_actual_costs
            estimated = project.estimated_budget
            forecast = PredictiveFinanceService.forecast_valuation(project)
            
            prompt = (
                f"You are a Senior ERP Financial Strategist. Project: {project.name}. "
                f"Budget: {estimated}, Actual: {actual}, Predicted Final Value: {forecast}. "
                f"Sector: Construction/Real-Estate. "
                "Provide a clear, 2-line strategic assessment in Arabic. "
                "Focus on 'Project ROI' and 'Burn Rate'. Use professional ERP terminology."
            )
            
            completion = client.chat.completions.create(
                model=dj_settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"لم يتمكن المحرك الذكي من الوصول للبيانات: {str(e)}"

"""
Personalization Service for User Awareness Sprint.

Provides:
- Personalized greetings based on timezone + name
- Activity-based quick action filtering
- Task ranking based on user activities
- Relevant data field prioritization
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz

from app.services.user_context import UserProfile


class PersonalizationService:
    """Service for generating personalized content based on user profile."""
    
    def generate_greeting(self, user_profile: UserProfile) -> str:
        """Generate a personalized greeting based on user's timezone and name.
        
        Args:
            user_profile: The user's profile
            
        Returns:
            Personalized greeting string like "Good morning, Sarah"
        """
        if not user_profile.greeting_enabled:
            return ""
        
        # Get time of day in user's timezone
        try:
            tz = pytz.timezone(user_profile.timezone)
            user_time = datetime.now(tz)
            hour = user_time.hour
        except Exception:
            # Fallback to generic greeting if timezone fails
            hour = 12
        
        # Determine greeting based on time
        if 5 <= hour < 12:
            time_greeting = "Good morning"
        elif 12 <= hour < 17:
            time_greeting = "Good afternoon"
        elif 17 <= hour < 21:
            time_greeting = "Good evening"
        else:
            time_greeting = "Hello"
        
        # Combine with name
        name = user_profile.greeting_name
        return f"{time_greeting}, {name}"
    
    def get_quick_actions_for_user(
        self,
        user_profile: UserProfile,
        max_actions: int = 5
    ) -> List[Dict[str, str]]:
        """Get quick actions filtered to user's activities.
        
        Args:
            user_profile: The user's profile
            max_actions: Maximum number of actions to return
            
        Returns:
            List of quick actions with code and label
        """
        # Return user's aggregated quick actions, limited
        actions = user_profile.quick_actions[:max_actions]
        return actions
    
    def get_relevant_data_fields(self, user_profile: UserProfile) -> List[str]:
        """Get data fields relevant to user's activities.
        
        Args:
            user_profile: The user's profile
            
        Returns:
            List of data field names to prioritize
        """
        return user_profile.relevant_data_fields
    
    def rank_tasks_for_user(
        self,
        tasks: List[Dict[str, Any]],
        user_profile: UserProfile
    ) -> List[Dict[str, Any]]:
        """Rank tasks based on how well they match user's activities.
        
        Tasks that match the user's activities are ranked higher.
        
        Args:
            tasks: List of task dictionaries with 'activity_type' or 'task_code'
            user_profile: The user's profile
            
        Returns:
            Sorted list of tasks with 'activity_match' flag added
        """
        user_activities = set(user_profile.activity_codes)
        
        def task_score(task: Dict) -> tuple:
            """Score a task - higher is better (more relevant to user)."""
            activity_type = task.get("activity_type") or task.get("task_code", "")
            
            # Map common task types to activities
            activity_mapping = {
                "eligibility": "verify_eligibility",
                "verify_eligibility": "verify_eligibility",
                "claim": "submit_claims",
                "submit_claim": "submit_claims",
                "denial": "rework_denials",
                "rework_denial": "rework_denials",
                "auth": "prior_authorization",
                "prior_auth": "prior_authorization",
                "schedule": "schedule_appointments",
                "appointment": "schedule_appointments",
                "check_in": "check_in_patients",
                "outreach": "patient_outreach",
                "referral": "coordinate_referrals",
            }
            
            mapped_activity = activity_mapping.get(activity_type, activity_type)
            matches = mapped_activity in user_activities
            
            # Priority: 1 = high, 5 = low. Lower is better.
            priority = task.get("priority", 3)
            
            # Return (matches, -priority) so matches=True sorts first, then by priority
            return (matches, -priority)
        
        # Sort tasks
        ranked_tasks = []
        for task in tasks:
            task_copy = task.copy()
            activity_type = task.get("activity_type") or task.get("task_code", "")
            
            # Check if task matches user's activities
            activity_mapping = {
                "eligibility": "verify_eligibility",
                "verify_eligibility": "verify_eligibility",
                "claim": "submit_claims",
                "submit_claim": "submit_claims",
                "denial": "rework_denials",
                "rework_denial": "rework_denials",
                "auth": "prior_authorization",
                "prior_auth": "prior_authorization",
                "schedule": "schedule_appointments",
                "appointment": "schedule_appointments",
                "check_in": "check_in_patients",
                "outreach": "patient_outreach",
                "referral": "coordinate_referrals",
            }
            mapped_activity = activity_mapping.get(activity_type, activity_type)
            task_copy["activity_match"] = mapped_activity in user_activities
            task_copy["matched_activity"] = mapped_activity if task_copy["activity_match"] else None
            
            ranked_tasks.append(task_copy)
        
        # Sort: matching tasks first, then by priority
        ranked_tasks.sort(key=lambda t: (not t["activity_match"], t.get("priority", 3)))
        
        return ranked_tasks
    
    def get_tone_instructions(self, user_profile: UserProfile) -> str:
        """Get tone instructions for LLM prompts based on user preference.
        
        Args:
            user_profile: The user's profile
            
        Returns:
            Instruction string for LLM
        """
        tone_instructions = {
            "professional": "Respond in a professional, clear, and concise manner. Use formal language.",
            "friendly": "Respond in a friendly, warm, and approachable manner. Be conversational but helpful.",
            "concise": "Respond with minimal words. Be direct and to the point. Omit pleasantries.",
        }
        return tone_instructions.get(user_profile.tone, tone_instructions["professional"])
    
    def build_personalization_payload(
        self,
        user_profile: UserProfile,
        include_greeting: bool = True,
        max_quick_actions: int = 5
    ) -> Dict[str, Any]:
        """Build the complete personalization payload for API response.
        
        Args:
            user_profile: The user's profile
            include_greeting: Whether to include greeting
            max_quick_actions: Maximum quick actions to include
            
        Returns:
            Dictionary with all personalization data
        """
        return {
            "greeting": self.generate_greeting(user_profile) if include_greeting else None,
            "tone": user_profile.tone,
            "quick_actions": self.get_quick_actions_for_user(user_profile, max_quick_actions),
            "prioritized_fields": self.get_relevant_data_fields(user_profile),
            "default_execution_mode": {
                "routine": user_profile.get_default_execution_mode(is_sensitive=False),
                "sensitive": user_profile.get_default_execution_mode(is_sensitive=True),
            },
        }
    
    def filter_tasks_for_user(
        self,
        tasks: List[Dict[str, Any]],
        user_profile: UserProfile,
        include_non_matching: bool = True,
        max_tasks: int = 10
    ) -> Dict[str, Any]:
        """Filter and rank tasks for a user.
        
        Args:
            tasks: List of tasks
            user_profile: The user's profile
            include_non_matching: Whether to include tasks that don't match activities
            max_tasks: Maximum tasks to return
            
        Returns:
            Dictionary with matched and other tasks
        """
        ranked = self.rank_tasks_for_user(tasks, user_profile)
        
        matched = [t for t in ranked if t.get("activity_match")]
        non_matched = [t for t in ranked if not t.get("activity_match")]
        
        if include_non_matching:
            all_tasks = matched + non_matched
        else:
            all_tasks = matched
        
        return {
            "tasks_for_you": matched[:max_tasks],
            "other_tasks": non_matched[:max_tasks] if include_non_matching else [],
            "total_matched": len(matched),
            "total_tasks": len(tasks),
        }


# Singleton instance
_personalization_service = None

def get_personalization_service() -> PersonalizationService:
    """Get the singleton personalization service instance."""
    global _personalization_service
    if _personalization_service is None:
        _personalization_service = PersonalizationService()
    return _personalization_service

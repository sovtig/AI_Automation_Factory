"""
Feedback Loop System for AI Automation Factory

A streamlined feedback collection and analysis system.
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from loguru import logger

class FeedbackType(str, Enum):
    """Types of feedback."""
    RATING = "rating"
    THUMBS = "thumbs"
    CORRECTION = "correction"
    COMMENT = "comment"
    BUG = "bug"
    FEATURE = "feature"

class Feedback(BaseModel):
    """Feedback data model."""
    type: FeedbackType
    task_id: Optional[str] = None
    content: Dict[str, Any] = {}
    user_id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class FeedbackSystem:
    """Manages feedback collection and analysis."""
    
    def __init__(self):
        self.feedback_store = []
        logger.info("Feedback system initialized")
    
    def submit(self, feedback: Dict) -> Dict:
        """Submit new feedback."""
        try:
            fb = Feedback(**feedback)
            self.feedback_store.append(fb)
            return {"status": "success", "id": len(self.feedback_store)}
        except Exception as e:
            logger.error(f"Feedback error: {e}")
            return {"status": "error", "message": str(e)}
    
    def analyze(self, days: int = 30) -> Dict:
        """Analyze recent feedback."""
        since = datetime.utcnow() - timedelta(days=days)
        recent = [f for f in self.feedback_store if f.created_at >= since]
        
        if not recent:
            return {"message": "No recent feedback"}
        
        # Count by type
        counts = {t: 0 for t in FeedbackType}
        for fb in recent:
            counts[fb.type] += 1
        
        # Calculate average rating if applicable
        ratings = [f.content['score'] for f in recent 
                  if f.type == FeedbackType.RATING and 'score' in f.content]
        
        return {
            "total": len(recent),
            "counts": {k.value: v for k, v in counts.items() if v > 0},
            "avg_rating": sum(ratings)/len(ratings) if ratings else None,
            "since": since.isoformat()
        }
    
    def get_low_ratings(self, threshold: int = 3) -> List[Dict]:
        """Get feedback with ratings below threshold."""
        return [
            {"id": i, "rating": f.content['score'], "task": f.task_id}
            for i, f in enumerate(self.feedback_store)
            if f.type == FeedbackType.RATING and 'score' in f.content 
            and f.content['score'] < threshold
        ]

# Example usage
if __name__ == "__main__":
    # Initialize feedback system
    feedback_system = FeedbackSystem()
    
    # Submit sample feedback
    feedback_system.submit({
        "type": "rating",
        "task_id": "task_123",
        "content": {"score": 4},
        "user_id": 1
    })
    
    # Analyze feedback
    print("Analysis:", feedback_system.analyze())

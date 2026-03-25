"""
Alliance Terminal — Advanced Logic & Cognitive Engine
Implements biological constraints, ripple rescheduling (eviction/re-packing), 
deadline gravity, and cognitive load balancing.
"""

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field

log = logging.getLogger("normandy.mood")

# Configuration & Paths
SCRIPT_DIR = Path(__file__).parent
SCHEDULE_PATH = SCRIPT_DIR / "schedule_history.json"

# --- PYDANTIC SCHEMAS (Extraction Layer Interface) ---

class UserIntent(BaseModel):
    action: Literal["create", "modify", "delete"] = Field("create", description="Operation to perform.")
    intent_type: Literal["fixed_event", "floating_task", "status_update"] = Field(
        description="'fixed_event' for rigid times. 'floating_task' for flexible chores. 'status_update' for sleep/wake/energy."
    )
    event_name: str
    start_time_reference: Optional[str] = Field(None, description="e.g., 'now', '9am', '14:00'.")
    end_time_reference: Optional[str] = Field(None, description="e.g., '11pm'.")
    duration_minutes: Optional[int] = Field(60, description="Inferred duration.")
    priority: int = Field(5, ge=1, le=10, description="Priority scale 1-10.")
    deadline: Optional[str] = Field(None, description="ISO format deadline string.")

class ParsedInput(BaseModel):
    intents: List[UserIntent]

# --- CORE LOGIC ENGINE ---

class MoodEngine:
    def __init__(self, state_file: str = "schedule_history.json"):
        self.state_file = Path(SCRIPT_DIR / state_file)
        self.schedule_db: Dict[str, List[Dict[str, Any]]] = {}
        self.overflow_queue: List[Dict[str, Any]] = []
        self._load_state()

    def _load_state(self):
        """Loads persistent JSON state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.schedule_db = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.schedule_db = {}
        else:
            self.schedule_db = {}

    def _save_state(self):
        """Saves current state to disk."""
        with open(self.state_file, 'w') as f:
            json.dump(self.schedule_db, f, indent=2)

    def _init_day(self, target_date: str):
        """Ensures a date entry exists and runs daily biological checks."""
        if target_date not in self.schedule_db:
            self.schedule_db[target_date] = []
            self._inject_daily_biological_anchors(target_date)

    def _inject_daily_biological_anchors(self, target_date: str):
        """Anchors meals and checks for sleep debt recovery."""
        # Standard Biological Anchors (Priority 8 for main meals, 4 for snacks)
        self._force_slot(target_date, "08:30", 45, "Breakfast", 8, "meal")
        self._force_slot(target_date, "12:30", 60, "Lunch", 8, "meal")
        self._force_slot(target_date, "15:30", 15, "Snack", 4, "meal")
        self._force_slot(target_date, "19:00", 60, "Dinner", 8, "meal")
        
        # Check Sleep Debt
        debt_mins = self._calculate_sleep_debt(target_date)
        if debt_mins > 0:
            log.info(f"Sleep debt detected: {debt_mins}m. Injecting recovery protocol.")
            # Auto-inject a Powernap in the afternoon (14:00 - 16:00 window)
            self.queue_flexible(target_date, "Powernap (Sleep Recovery)", 45, 9, "afternoon")

    def _calculate_sleep_debt(self, target_date: str) -> int:
        """Calculates yesterday's sleep deficit below a 7-hour threshold."""
        yest = (date.fromisoformat(target_date) - timedelta(days=1)).isoformat()
        if yest not in self.schedule_db:
            return 0
        
        # Filter activities that contain "sleep"
        sleep_events = [t for t in self.schedule_db[yest] if "sleep" in t["activity"].lower()]
        total_sleep = sum(t["duration"] for t in sleep_events)
        
        threshold = 7 * 60 # 420 minutes
        return max(0, threshold - total_sleep) if total_sleep > 0 else 0

    def get_context_for_ai(self) -> str:
        """Injects hardware time and biological constraints into the AI system prompt."""
        now = datetime.now()
        today_str = now.date().isoformat()
        self._init_day(today_str)
        
        debt_mins = self._calculate_sleep_debt(today_str)
        context = [
            f"SYSTEM TIME: {now.strftime('%H:%M')}",
            f"SYSTEM DATE: {today_str}",
        ]
        
        if debt_mins > 0:
            context.append(f"[BIOMEDICAL ALERT] CRITICAL SLEEP DEBT: {debt_mins} minutes deficit detected. Focus protocols degraded.")
        
        # Current Schedule Overview
        context.append("\n[CURRENT OPERATIONS SCHEDULE]")
        day_tasks = self.schedule_db.get(today_str, [])
        # Safe sort: skip items missing 'start_time'
        valid_tasks = [t for t in day_tasks if "start_time" in t]
        for t in sorted(valid_tasks, key=lambda x: x['start_time']):
            # Apply Deadline Gravity for context view
            pri = self._apply_deadline_gravity(t.get('priority', 5), t.get('deadline'))
            context.append(f"- {t['start_time']} ({t['duration']}m) [P{pri}]: {t['activity']}")
            
        if self.overflow_queue:
            context.append("\n[OVERFLOW QUEUE - AWAITING RE-PACKING]")
            for o in self.overflow_queue:
                context.append(f"- {o['activity']} ({o['duration']}m) [P{o['priority']}]")
                
        return "\n".join(context)

    def process_parsed_input(self, data: ParsedInput):
        """Route Pydantic intents to specific execution logic."""
        for intent in data.intents:
            self._execute_intent(intent)
        self._save_state()

    def calculate_dynamic_wake_time(self, target_date: str) -> str:
        """Helper to find the earliest fixed event and subtract 1 hour."""
        tasks = self.schedule_db.get(target_date, [])
        if not tasks:
            return "08:00"
        
        fixed_times = []
        for t in tasks:
            h, m = map(int, t['start_time'].split(':'))
            fixed_times.append(h * 60 + m)
            
        if not fixed_times:
             return "08:00"
             
        earliest_m = min(fixed_times)
        wake_m = max(0, earliest_m - 60)
        return f"{wake_m // 60:02d}:{wake_m % 60:02d}"

    def execute_schedule_command(self, cmd: dict) -> bool:
        """Legacy-to-Logic bridge for commands from AIBackend."""
        try:
            # Handle both old and new field names for robustness
            intent = UserIntent(
                action=cmd.get("action", "create"),
                intent_type=cmd.get("intent_type") or ("fixed_event" if cmd.get("start_time") or cmd.get("start_time_reference") else "floating_task"),
                event_name=str(cmd.get("event_name", cmd.get("label", cmd.get("activity", "Unknown Operation")))),
                start_time_reference=cmd.get("start_time_reference", cmd.get("start_time")),
                duration_minutes=int(cmd.get("duration_minutes", cmd.get("duration", 60))),
                priority=int(cmd.get("priority", 5)),
                deadline=cmd.get("deadline")
            )
            success = self._execute_intent(intent)
            if success:
                self._save_state()
            return success
        except Exception as e:
            log.error(f"Error in execute_schedule_command bridge: {e}")
            return False

    def _parse_time_reference(self, ref: str) -> Optional[str]:
        """Parses keywords like 'midnight', 'noon', 'morning' into standard HH:MM."""
        if not ref: return None
        ref = ref.lower().strip()
        
        # Strict Keyword Mapping
        mapping = {
            "midnight": "00:00",
            "noon": "12:00",
            "midday": "12:00",
            "morning": "09:00",
            "afternoon": "13:00",
            "evening": "18:00",
            "tonight": "21:00",
            "night": "22:00",
            "now": datetime.now().strftime("%H:%M")
        }
        
        if ref in mapping:
            return mapping[ref]
        
        # Exact HH:MM check
        if ":" in ref:
             return ref
        return None

    def _execute_intent(self, intent: UserIntent) -> bool:
        """Internal executor for a single UserIntent."""
        target_date = date.today().isoformat()
        
        # Parse start_time_reference if it's relative
        if intent.start_time_reference:
            parsed = self._parse_time_reference(intent.start_time_reference)
            if parsed:
                intent.start_time_reference = parsed

        # Handle Deletions/Modifications by Name
        if intent.action in ["delete", "modify"]:
            # Search both today and tomorrow by default for deletions
            search_dates = [date.today().isoformat(), (date.today() + timedelta(days=1)).isoformat()]
            found = False
            for d_str in search_dates:
                tasks = self.schedule_db.get(d_str, [])
                # Fuzzy match: case-insensitive and check if event_name is in activity OR activity is in event_name
                # This helps if user says "midnight snack" and it's just "Snack" (or vice versa)
                new_tasks = [
                    t for t in tasks 
                    if not (intent.event_name.lower() in t['activity'].lower() or t['activity'].lower() in intent.event_name.lower())
                ]
                if len(new_tasks) < len(tasks):
                    self.schedule_db[d_str] = new_tasks
                    found = True
            
            if found and intent.action == "delete":
                return True
            # If modify, we fall through with the cleaned schedule (where possible)
            
        # --- NEXT OCCURRENCE LOGIC ---
        # If a time is provided and it has already passed today, assume it's for tomorrow.
        now = datetime.now()
        if intent.start_time_reference and ":" in intent.start_time_reference:
            try:
                h, m = map(int, intent.start_time_reference.split(':'))
                if h * 60 + m < now.hour * 60 + now.minute:
                    # Time has passed, move to tomorrow
                    target_date = (date.today() + timedelta(days=1)).isoformat()
                    log.info(f"Time {intent.start_time_reference} has passed today. Scheduling for tomorrow ({target_date}).")
                elif h == 0 and m == 0: # Midnight specifically
                     # If it's late at night (e.g. after 9pm), midnight means tomorrow
                     if now.hour >= 21:
                         target_date = (date.today() + timedelta(days=1)).isoformat()
                         log.info(f"Late night request for midnight. Scheduling for tomorrow ({target_date}).")
            except Exception:
                pass

        # --- PRIORITY HIERARCHY / FLEXIBILITY RULES ---
        # School/Fixed Items (P9)
        school_keywords = ["class", "lecture", "exam", "school", "university", "seminar"]
        if any(k in intent.event_name.lower() for k in school_keywords):
            intent.priority = max(intent.priority, 9)
            
        # Meals (P8)
        meal_keywords = ["lunch", "dinner", "breakfast", "meal"]
        if any(k in intent.event_name.lower() for k in meal_keywords):
            intent.priority = max(intent.priority, 8)

        if intent.intent_type == "fixed_event":
            return self._force_slot(
                target_date, 
                intent.start_time_reference or "12:00", 
                intent.duration_minutes or 60,
                intent.event_name,
                intent.priority,
                "task",
                intent.deadline or ""
            )
        elif intent.intent_type == "floating_task":
            return self.queue_flexible(
                target_date,
                intent.event_name,
                intent.duration_minutes or 60,
                intent.priority,
                intent.start_time_reference or "now",
                intent.deadline or ""
            )
        elif intent.intent_type == "status_update":
            if "sleep" in intent.event_name.lower():
                # Sleep is P8: Can be pushed by School (P9) but beats low-pri tasks
                # For late night sleep requests, it's often for the 'next' day if after 00:00
                return self._force_slot(target_date, "00:00", intent.duration_minutes or 420, "Sleep", 8, "sleep")
        return False

    def check_reminders(self) -> List[str]:
        """Checks for upcoming tasks and returns HTML reminder strings."""
        now = datetime.now()
        reminders = []
        today_str = now.date().isoformat()
        day_tasks = self.schedule_db.get(today_str, [])
        now_m = now.hour * 60 + now.minute
        
        for t in day_tasks:
            h, m = map(int, t['start_time'].split(':'))
            sm = h * 60 + m
            diff = sm - now_m
            
            # Use task name + time for uniqueness
            key = f"{t['start_time']}_{t['activity']}"
            if 0 < diff <= 15: # Reminder within 15 mins
                reminders.append(
                    f"Heads up — <b>{t['activity']}</b> begins at <b>{t['start_time']}</b>. "
                    f"That's in {diff} minutes."
                )
        return reminders

    def get_mood(self) -> dict:
        """Predicts agent 'mood' based on time of day."""
        h = datetime.now().hour
        # Simplified Mass Effect style mood table
        table = [
            (5, 8, "REVEILLE", "Rising phase. Cortisol levels normalizing.", "#00ccff"),
            (8, 12, "COMBAT READY", "Peak cognitive function detected.", "#00ff88"),
            (12, 14, "REFUEL WINDOW", "Midday maintenance.", "#f2a900"),
            (14, 18, "PEAK OPS", "High-intensity operations active.", "#00ff88"),
            (18, 22, "WIND DOWN", "Recovery cycle approaching.", "#f2a900"),
            (22, 5, "RECOVERY", "Sleep critical for combat effectiveness.", "#ff0033")
        ]
        for s, e, l, d, c in table:
            if s <= h < e if s < e else (h >= s or h < e):
                return {"label": l, "description": d, "color": c}
        return {"label": "NOMINAL", "description": "Systems stable.", "color": "#00ccff"}

    def get_mood_html(self) -> str:
        """Returns HTML-formatted mood status for UI injection."""
        mood = self.get_mood()
        time_str = datetime.now().strftime("%H:%M")
        return (
            f"<div style='padding: 10px; border-left: 3px solid {mood['color']}; background: rgba(0,40,80,0.15);'>"
            f"<div style='font-family: Orbitron, sans-serif; font-size: 11px; color: {mood['color']}; letter-spacing: 2px; margin-bottom: 4px;'>"
            f"STATUS: {mood['label']}</div>"
            f"<div style='font-family: Montserrat, sans-serif; font-size: 12px; color: #c0d0e0; font-weight: 300;'>"
            f"{mood['description']}</div>"
            f"<div style='font-family: Orbitron, sans-serif; font-size: 9px; color: #445566; margin-top: 6px;'>"
            f"LOCAL TIME: {time_str}</div></div>"
        )

    def get_schedule_html(self) -> str:
        """HTML rendering of current schedule for rolling 36h window."""
        now = datetime.now()
        start_win = now - timedelta(hours=12)
        end_win = now + timedelta(hours=24)
        
        dates = [(now + timedelta(days=i)).date().isoformat() for i in [-1, 0, 1]]
        all_tasks = []
        
        for d_str in dates:
            day_tasks = self.schedule_db.get(d_str, [])
            for t in day_tasks:
                if "start_time" not in t: continue
                h, m = map(int, t['start_time'].split(':'))
                dt = datetime.fromisoformat(d_str).replace(hour=h, minute=m)
                
                if start_win <= dt <= end_win:
                    t_copy = t.copy()
                    t_copy['_abs_dt'] = dt
                    all_tasks.append(t_copy)
                    
        # --- WINDOW EXPANSION ---
        if not all_tasks:
            # If 36h window is empty, show all future events
            for d_str, day_tasks in self.schedule_db.items():
                for t in day_tasks:
                    if "start_time" not in t: continue
                    h, m = map(int, t['start_time'].split(':'))
                    dt = datetime.fromisoformat(d_str).replace(hour=h, minute=m)
                    if dt >= now:
                        t_copy = t.copy()
                        t_copy['_abs_dt'] = dt
                        all_tasks.append(t_copy)

        if not all_tasks:
            return "<div style='color: #4a5568; padding: 10px;'>[NO OPERATIONS SCHEDULED]</div>"
            
        parts = []
        for t in sorted(all_tasks, key=lambda x: x['_abs_dt']):
            dt = t['_abs_dt']
            is_active = dt <= now < dt + timedelta(minutes=t['duration'])
            curr_class = " current" if is_active else ""
            pri_color = "var(--orange-n7)" if t.get('priority', 5) >= 8 else "var(--text-dim)"
            
            parts.append(
                f"<div class='schedule-entry{curr_class}'>"
                f"<span style='color: var(--cyan-bright); font-family: Orbitron, monospace; font-size: 13px; letter-spacing: 1px; font-weight: bold;'>{t['start_time']}</span> "
                f"<span class='schedule-task'>{t['activity']}</span> "
                f"<span style='color: {pri_color}; font-size: 0.8em;'>({t['duration']}m)</span>"
                f"</div>"
            )
        return "".join(parts)

    def _apply_deadline_gravity(self, base_priority: int, deadline: Optional[str]) -> int:
        """Scales priority based on proximity to ISO deadline."""
        if not deadline:
            return base_priority
        try:
            dl_dt = datetime.fromisoformat(deadline)
            now = datetime.now()
            hours_left = (dl_dt - now).total_seconds() / 3600
            
            if hours_left <= 0: return 10
            if hours_left < 12: return min(10, base_priority + 3)
            if hours_left < 24: return min(10, base_priority + 2)
            if hours_left < 48: return min(10, base_priority + 1)
        except Exception:
            pass
        return base_priority

    def _force_slot(self, target_date: str, start_time: str, duration: int, activity: str, priority: int, t_type: str = "task", deadline: str = "") -> bool:
        """The Ripple Rescheduler: Evicts lower-priority overlaps and re-queues them."""
        self._init_day(target_date)
        
        # Calculate numeric time frames
        h, m = map(int, start_time.split(':'))
        new_start = h * 60 + m
        new_end = new_start + duration
        
        effective_priority = self._apply_deadline_gravity(priority, deadline)
        
        survivors = []
        evicted = []
        
        # Check overlaps
        for task in self.schedule_db[target_date]:
            th, tm = map(int, task['start_time'].split(':'))
            ts = th * 60 + tm
            te = ts + task['duration']
            
            if not (new_end <= ts or new_start >= te):
                # Overlap detected
                task_pri = self._apply_deadline_gravity(task['priority'], task.get('deadline'))
                
                # Special Case: Allow pushing 'Sleep' start time for user requests
                if task['activity'].lower() == "sleep" and new_start < 120: # If it's early morning conflict
                    log.warning(f"Pushing Sleep start for '{activity}'")
                    task['start_time'] = f"{h:02d}:{m+duration:02d}" if m+duration < 60 else f"{h+(m+duration)//60:02d}:{(m+duration)%60:02d}"
                    task['duration'] -= duration
                    survivors.append(task)
                    continue

                if task_pri < effective_priority:
                    log.warning(f"Evicting '{task['activity']}' for higher priority '{activity}'")
                    evicted.append(task)
                else:
                    log.error(f"Cannot slot '{activity}': Blocked by higher priority '{task['activity']}'")
                    return False
            else:
                survivors.append(task)
        
        # Add new task
        survivors.append({
            "start_time": f"{h:02d}:{m:02d}",
            "duration": duration,
            "activity": activity,
            "priority": priority,
            "type": t_type,
            "deadline": deadline
        })
        
        # Re-sort and save
        survivors.sort(key=lambda x: x['start_time'])
        self.schedule_db[target_date] = survivors
        
        # Attempt to re-pack evicted tasks
        for item in evicted:
            self.queue_flexible(target_date, item['activity'], item['duration'], item['priority'], "now", item.get('deadline'))
            
        return True

    def queue_flexible(self, target_date: str, activity: str, duration: int, priority: int, window: str = "now", deadline: str = "") -> bool:
        """The Gap Finder with Cognitive Load Balancing and Cross-Day Repacking."""
        self._init_day(target_date)
        now = datetime.now()
        
        # Define search window in minutes-since-midnight
        w_start, w_end = 0, 23 * 60 + 59
        window = window.lower()
        if "morning" in window: w_start, w_end = 6 * 60, 12 * 60
        elif "afternoon" in window: w_start, w_end = 12 * 60, 18 * 00
        elif "evening" in window: w_start, w_end = 18 * 00, 23 * 59
        elif "now" in window and target_date == now.date().isoformat():
            w_start = now.hour * 60 + now.minute + 1
        elif ":" in window: # Specific time like "00:00"
            wh, wm = map(int, window.split(':'))
            w_start = wh * 60 + wm
            
        # Get existing blocks
        blocks = []
        for t in self.schedule_db[target_date]:
            th, tm = map(int, t['start_time'].split(':'))
            ts = th * 60 + tm
            blocks.append((ts, ts + t['duration'], t['priority']))
        blocks.sort()
        
        # Linear search for first gap
        cursor = w_start
        while cursor + duration <= w_end:
            # --- Cognitive Load Check ---
            # If 4 straight hours of P8+ work exist, enforce 15m buffer
            if self._is_cognitive_overloaded(target_date, cursor) and priority >= 8:
                log.info(f"Cognitive load exceeds threshold. Adding 15m buffer before '{activity}'.")
                cursor += 15
                continue
                
            collision = False
            for bs, be, bp in blocks:
                if not (cursor + duration <= bs or cursor >= be):
                    collision = True
                    cursor = be
                    break
            
            if not collision:
                # Slot found!
                h, m = cursor // 60, cursor % 60
                return self._force_slot(target_date, f"{h:02d}:{m:02d}", duration, activity, priority, "task", deadline)
            
        # No gap today? Try tomorrow.
        tomorrow = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()
        if target_date != tomorrow and "tomorrow" not in window: # Avoid infinite loop
             log.info(f"No gap for '{activity}' today. Attempting tomorrow...")
             return self.queue_flexible(tomorrow, activity, duration, priority, "morning", deadline)
             
        # Finally relegate to overflow
        log.warning(f"Relegating '{activity}' to overflow queue.")
        self.overflow_queue.append({
            "activity": activity, "duration": duration, "priority": priority, "deadline": deadline
        })
        return False

    def _is_cognitive_overloaded(self, target_date: str, start_min: int) -> bool:
        """Heuristic: Checks if the previous 4 hours contain >240m of P8+ activity."""
        window_start = int(max(0, start_min - 240))
        high_intensity_mins = 0
        
        for t in self.schedule_db.get(target_date, []):
            th, tm = map(int, t['start_time'].split(':'))
            ts = int(th * 60 + tm)
            te = int(ts + int(t['duration']))
            
            # Check if task is P8+ and overlaps with the 4-hour window
            if int(t['priority']) >= 8:
                overlap_s = int(max(window_start, ts))
                overlap_e = int(min(start_min, te))
                if overlap_s < overlap_e:
                    high_intensity_mins += int(overlap_e - overlap_s)
                    
        return high_intensity_mins >= 240

# --- MODULE TEST / USAGE EXAMPLES ---
if __name__ == "__main__":
    engine = MoodEngine()
    
    # Mock some Test Data Context for the User intents
    test_input = ParsedInput(intents=[
        # P9 Flexible Afternoon (120m)
        UserIntent(intent_type="floating_task", event_name="Study for Physics/Math Mid-terms", duration_minutes=120, priority=9, start_time_reference="afternoon"),
        
        # P8 Hard Slot (60m at 14:00)
        UserIntent(intent_type="fixed_event", event_name="Baggage Scanner YOLO project group meeting", start_time_reference="14:00", duration_minutes=60, priority=8),
        
        # P5 Flexible Evening (180m block)
        UserIntent(intent_type="floating_task", event_name="Blender animation rendering", duration_minutes=180, priority=5, start_time_reference="evening"),
        
        # P2 Flexible Evening (90m)
        UserIntent(intent_type="floating_task", event_name="Play Mass Effect", duration_minutes=90, priority=2, start_time_reference="evening")
    ])
    
    print("--- BOOTING LOGIC LAYER ---")
    engine.process_parsed_input(test_input)
    print(engine.get_context_for_ai())
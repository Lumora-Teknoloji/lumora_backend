"""
Command Queue endpoint for bot launcher service
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import threading

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

# In-memory command queue
_command_queue = []
_queue_lock = threading.Lock()

class BotCommand(BaseModel):
    id: int
    type: str  # "START" or "STOP"
    task_id: int
    target_url: Optional[str] = None
    created_at: datetime

class CommandAck(BaseModel):
    success: bool
    message: str


@router.get("/commands", response_model=List[BotCommand])
async def get_pending_commands():
    """Get pending bot commands for Windows launcher service"""
    with _queue_lock:
        # Return all pending commands
        return _command_queue.copy()


@router.post("/commands/{command_id}/ack")
async def acknowledge_command(command_id: int, ack: CommandAck):
    """Acknowledge command execution"""
    with _queue_lock:
        # Remove acknowledged command from queue
        global _command_queue
        _command_queue = [cmd for cmd in _command_queue if cmd.id != command_id]
    
    return {"success": True, "message": "Command acknowledged"}


def queue_bot_command(cmd_type: str, task_id: int, target_url: str = ""):
    """Add command to queue"""
    with _queue_lock:
        cmd_id = len(_command_queue) + int(datetime.now().timestamp())
        command = BotCommand(
            id=cmd_id,
            type=cmd_type,
            task_id=task_id,
            target_url=target_url,
            created_at=datetime.now()
        )
        _command_queue.append(command)
        return command

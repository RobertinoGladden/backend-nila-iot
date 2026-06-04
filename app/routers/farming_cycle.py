"""Farming cycle management router"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.farming_service import (
    create_farming_cycle, get_farming_cycle, get_user_farming_cycles,
    get_active_farming_cycle, calculate_farming_days, update_farming_cycle,
    get_farming_cycle_stats, delete_farming_cycle
)
from app.schemas import (
    FarmingCycleCreate, FarmingCycleResponse, FarmingCycleUpdate
)

router = APIRouter(prefix="/farming-cycle", tags=["Farming Cycles"])



@router.post("/", response_model=FarmingCycleResponse)
def start_farming_cycle(
    cycle_data: FarmingCycleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new farming cycle
    """
    try:
        cycle = create_farming_cycle(db, user.id, cycle_data)
        return cycle
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create farming cycle: {str(e)}")


@router.get("/", response_model=List[FarmingCycleResponse])
def list_farming_cycles(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all farming cycles for the current user
    """
    cycles = get_user_farming_cycles(db, user.id)
    return cycles


@router.get("/active", response_model=Optional[FarmingCycleResponse])
def get_active_cycle(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the currently active farming cycle
    """
    cycle = get_active_farming_cycle(db, user.id)
    if not cycle:
        raise HTTPException(status_code=404, detail="No active farming cycle found")
    return cycle


@router.get("/{cycle_id}", response_model=FarmingCycleResponse)
def get_cycle(
    cycle_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific farming cycle by ID
    """
    cycle = get_farming_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Farming cycle not found")
    
    if cycle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return cycle


@router.put("/{cycle_id}", response_model=FarmingCycleResponse)
def update_cycle(
    cycle_id: int,
    update_data: FarmingCycleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a farming cycle
    """
    cycle = get_farming_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Farming cycle not found")
    
    if cycle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        updated_cycle = update_farming_cycle(db, cycle_id, update_data)
        return updated_cycle
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update cycle: {str(e)}")


@router.delete("/{cycle_id}", response_model=dict)
def delete_cycle(
    cycle_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a farming cycle (and its related feed data)
    """
    cycle = get_farming_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Farming cycle not found")

    if cycle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        deleted = delete_farming_cycle(db, cycle_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Farming cycle not found")
        return {"message": "Farming cycle berhasil dihapus", "cycle_id": cycle_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete cycle: {str(e)}")


@router.get("/{cycle_id}/days", response_model=dict)
def get_farming_days_endpoint(
    cycle_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get number of farming days for a cycle
    """
    cycle = get_farming_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Farming cycle not found")
    
    if cycle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    days = calculate_farming_days(cycle.seeding_date)
    return {
        "cycle_id": cycle_id,
        "farming_days": days,
        "seeding_date": cycle.seeding_date,
        "status": cycle.status
    }


@router.get("/{cycle_id}/stats", response_model=dict)
def get_cycle_stats(
    cycle_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics for a farming cycle
    """
    cycle = get_farming_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Farming cycle not found")
    
    if cycle.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    stats = get_farming_cycle_stats(db, cycle_id)
    return stats

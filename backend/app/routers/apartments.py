from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Apartment, ApartmentPhoto, PriceOverride, User
from ..schemas import ApartmentIn, ApartmentOut, ApartmentPatch, PriceOverrideIn
from ..security import owner_only, staff
from ..services.files import IMAGE_EXT, save_upload

router = APIRouter(prefix="/apartments", tags=["apartments"])


def get_own_apartment(db: Session, user: User, apartment_id: int) -> Apartment:
    apt = db.get(Apartment, apartment_id)
    if apt is None or apt.account_id != user.account_id:  # чужое = «не найдено», без утечки факта существования
        raise HTTPException(404, "Квартира не найдена")
    return apt


@router.get("", response_model=list[ApartmentOut])
def list_apartments(user: User = Depends(staff), db: Session = Depends(get_db)):
    return db.scalars(select(Apartment).where(Apartment.account_id == user.account_id).order_by(Apartment.id)).all()


@router.post("", response_model=ApartmentOut, status_code=201)
def create_apartment(data: ApartmentIn, user: User = Depends(owner_only), db: Session = Depends(get_db)):
    count = db.scalar(select(func.count()).select_from(Apartment).where(Apartment.account_id == user.account_id))
    if count >= settings.max_apartments_per_account:
        raise HTTPException(422, f"Лимит — {settings.max_apartments_per_account} квартир")
    apt = Apartment(account_id=user.account_id, **data.model_dump())
    db.add(apt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Квартира с такой ссылкой уже есть") from None
    return apt


@router.get("/{apartment_id}", response_model=ApartmentOut)
def get_apartment(apartment_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    return get_own_apartment(db, user, apartment_id)


@router.patch("/{apartment_id}", response_model=ApartmentOut)
def patch_apartment(apartment_id: int, data: ApartmentPatch, user: User = Depends(owner_only),
                    db: Session = Depends(get_db)):
    apt = get_own_apartment(db, user, apartment_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(apt, k, v)
    db.commit()
    return apt


@router.post("/{apartment_id}/photos", response_model=ApartmentOut, status_code=201)
def upload_photo(apartment_id: int, file: UploadFile = File(...), user: User = Depends(owner_only),
                 db: Session = Depends(get_db)):
    apt = get_own_apartment(db, user, apartment_id)
    if len(apt.photos) >= settings.max_photos_per_apartment:
        raise HTTPException(422, f"Не больше {settings.max_photos_per_apartment} фото")
    path = save_upload(file, "public/photos", IMAGE_EXT)
    apt.photos.append(ApartmentPhoto(path=path, position=len(apt.photos)))
    db.commit()
    db.refresh(apt)
    return apt


@router.delete("/{apartment_id}/photos/{photo_id}", status_code=204)
def delete_photo(apartment_id: int, photo_id: int, user: User = Depends(owner_only), db: Session = Depends(get_db)):
    apt = get_own_apartment(db, user, apartment_id)
    photo = next((p for p in apt.photos if p.id == photo_id), None)
    if photo is None:
        raise HTTPException(404, "Фото не найдено")
    apt.photos.remove(photo)
    db.commit()


@router.put("/{apartment_id}/prices", status_code=204)
def set_price_override(apartment_id: int, data: PriceOverrideIn, user: User = Depends(owner_only),
                       db: Session = Depends(get_db)):
    apt = get_own_apartment(db, user, apartment_id)
    existing = db.scalar(select(PriceOverride).where(PriceOverride.apartment_id == apt.id,
                                                     PriceOverride.night == data.night))
    if existing:
        existing.price = data.price
    else:
        db.add(PriceOverride(apartment_id=apt.id, night=data.night, price=data.price))
    db.commit()

# coding: utf-8
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from app.api.routes.profile import UserProfileRequest, save_profile, get_profile

def test_save_and_get_profile(engine):
    db = Session(engine)
    req = MagicMock()
    req.state = MagicMock()
    r = save_profile(UserProfileRequest(user_id='u1', age=25, gender='male', height_cm=175, weight_kg=70, activity_level='medium', health_goal='maintain'), request=req, db=db)
    assert r.user_id == 'u1'
    r2 = save_profile(UserProfileRequest(user_id='u1', age=26, gender='male', height_cm=175, weight_kg=68, activity_level='high', health_goal='lose_weight'), request=req, db=db)
    assert r2.age == 26
    nf = get_profile(user_id='nobody', db=db)
    assert isinstance(nf, dict)
    assert nf.get('detail') == 'not_found'
    db.close()

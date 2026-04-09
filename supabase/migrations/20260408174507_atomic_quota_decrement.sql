CREATE OR REPLACE FUNCTION decrement_user_quota(user_uuid UUID)
RETURNS void AS $$
BEGIN
  UPDATE profiles
  SET remaining_quota = GREATEST(0, remaining_quota - 1)
  WHERE id = user_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

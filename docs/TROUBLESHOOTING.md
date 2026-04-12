# Troubleshooting Guide

## Common Issues

### Backend won't start

**Check Python version:**
```bash
python --version  # Must be >=3.10
```

**Verify Poetry environment:**
```bash
poetry shell
poetry env info
```

**Reinstall dependencies:**
```bash
poetry lock --no-update
poetry install
```

**Port in use (Windows):**
```bash
netstat -ano | findstr :8000
# Kill process or change port: fastapi dev src/argus/api/main.py --host 127.0.0.1 --port 8001
```

### Frontend won't install

**Clear Bun cache and reinstall:**
```bash
bun pm cache rm
rm -r node_modules bun.lockb
bun install
```

### Mock Data Mode Not Working

Ensure `.env.local` contains:
```env
NEXT_PUBLIC_MOCK_API=true
```
Then restart the dev server:
```bash
cd web
bun run build
bun run dev
```

### Supabase Connection Fails

1. Verify `SUPABASE_URL` and `SUPABASE_ANON_KEY` in your `.env` files.
2. Test connectivity: visit `https://your-project.supabase.co/auth/v1/health`.
3. Check Row-Level Security (RLS) policies in the Supabase Dashboard if you encounter "permission denied" errors.

from supabase_config import supabase

# Replace this with a valid student_id from your Supabase students table
student_id = "CS203"

try:
    result = supabase.rpc("increment_attendance", {"student_id_input": student_id}).execute()
    print("✅ RPC executed successfully!")
    print("Response:", result)
except Exception as e:
    print("❌ Error running RPC:", e)

from supabase_config import supabase

print("✅ Connected successfully to Supabase!")

# Optional: Try fetching data from your teachers table
response = supabase.table("teachers").select("*").limit(2).execute()
print(response.data)

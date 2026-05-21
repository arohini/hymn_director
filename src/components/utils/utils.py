import time, functools

def retry_on_ratelimit(max_retries=5, initial_sleep=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print("started *"*30)
            sleep_time = initial_sleep
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if it's a Rate Limit error (429)
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        print(f"Rate limit hit. Retrying in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(sleep_time)
                        sleep_time *= 2  # Exponentially increase wait time
                    else:
                        raise e # Raise other errors immediately (Auth, Network, etc.)
            return None # Or raise a final exception
        return wrapper
    return decorator
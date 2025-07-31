import random
import time
import streamlit as st
import datetime
import hashlib

#  import Google Sheets dependencies
try:
    import gspread
    from google.oauth2.service_account import Credentials
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

# ----- Word List -----
WORDS = [
    "composability", "nontransferable", "participation", "reflections",
    "ownership", "flywheel", "deflation", "gamified", "ecosystem",
    "recursive", "shareincreasing", "volume", "airdrop", "internaltoken",
    "boosted", "trading", "utilityburn", "farming", "creativity", "rewards",
    "APY", "EthOS"
]

# Filter and normalize words
WORDS = [w.lower() for w in WORDS if 3 <= len(w) <= 15]

# ----- Configuration -----
MAX_GUESSES = 3
GUESS_TIME_LIMIT = 15  # seconds per guess
MAX_CONCURRENT_USERS = 50  # Maximum users playing at once


def cleanup_expired_sessions():
    """Remove sessions that have been inactive for more than 5 minutes"""
    if "active_users" not in st.session_state:
        st.session_state.active_users = {}
    
    current_time = time.time()
    expired_sessions = []
    
    for session_id, last_activity in st.session_state.active_users.items():
        if current_time - last_activity > 300:  # 5 minutes timeout
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        del st.session_state.active_users[session_id]

def get_current_user_count():
    """Get the current number of active users"""
    cleanup_expired_sessions()
    return len(st.session_state.active_users)

def register_user_session():
    """Register the current user session"""
    if "active_users" not in st.session_state:
        st.session_state.active_users = {}
    
   
    session_id = hashlib.md5(str(id(st.session_state)).encode()).hexdigest()
    st.session_state.active_users[session_id] = time.time()
    st.session_state.current_session_id = session_id

def check_user_limit():
    """Check if we're at the user limit"""
    current_users = get_current_user_count()
    
    # If user is already registered, let them continue
    if hasattr(st.session_state, 'current_session_id') and \
       st.session_state.current_session_id in st.session_state.get('active_users', {}):
        # Update their last activity time
        st.session_state.active_users[st.session_state.current_session_id] = time.time()
        return True, current_users
    
    # Check if we can accept a new user
    if current_users >= MAX_CONCURRENT_USERS:
        return False, current_users
    
    # Register new user
    register_user_session()
    return True, current_users + 1

def get_feedback(secret, guess):
    """Generate Wordle-style feedback for a guess"""
    feedback = []
    secret_chars = list(secret)
    guess_chars = list(guess)
    used = [False] * len(secret_chars)
    

    for i, ch in enumerate(guess_chars):
        if i < len(secret_chars) and ch == secret_chars[i]:
            feedback.append("🟩")  # correct spot
            used[i] = True
        else:
            feedback.append("")  # fill later
    
    # Pass 2: Mark correct letters in wrong positions
    for i, ch in enumerate(guess_chars):
        if feedback[i]:  # Already marked as correct position
            continue
        
        found = False
        for j, sch in enumerate(secret_chars):
            if not used[j] and ch == sch:
                found = True
                used[j] = True
                break
        
        if found:
            feedback[i] = "🟨"  # right letter, wrong spot
        else:
            feedback[i] = "⬜"  # not in word
    
    return "".join(feedback)

def submit_to_google_sheets(twitter_handle):
    """Submit winner data to Google Sheets"""
    if not SHEETS_AVAILABLE:
        return False, "Google Sheets libraries not available"
    
    try:
      
        if "gcp_service_account" not in st.secrets:
            return False, "Google Sheets credentials not configured in secrets"
        
       
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=scope
        )
        
      
        client = gspread.authorize(creds)
        
       
        sheet = client.open("Ethos Wordle Winners").sheet1
        
    
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        word_guessed = st.session_state.word
        num_guesses = len(st.session_state.guesses)
        
    
        sheet.append_row([
            timestamp,
            twitter_handle,
            word_guessed,
            num_guesses,
            "Winner"
        ])
        
        return True, "Successfully submitted to Google Sheets"
        
    except FileNotFoundError:
        return False, "Spreadsheet 'Ethos Wordle Winners' not found"
    except Exception as e:
        return False, f"Google Sheets error: {str(e)}"

def normalize_word(word):
    """Normalize word for comparison"""
    return word.strip().lower()

def reset_game():
    """Reset all game state"""
    keys_to_keep = ['active_users', 'current_session_id']
    keys_to_delete = [key for key in st.session_state.keys() if key not in keys_to_keep]
    
    for key in keys_to_delete:
        del st.session_state[key]

def initialize_game():
    """Initialize a new game"""
    st.session_state.word = random.choice(WORDS)
    st.session_state.guesses = []
    st.session_state.feedback = []
    st.session_state.start_time = time.time()
    st.session_state.guess_start_time = time.time()
    st.session_state.game_won = False
    st.session_state.finished = False
    st.session_state.game_started = True

# ----- Main Streamlit App -----
def main():
    st.set_page_config(
        page_title="Ethereum OS Wordle",
        page_icon="🎯",
        layout="centered"
    )
    
    st.title("🎯 Ethereum OS Wordle")
    st.write(
        "Guess the secret Ethereum OS term. Each word is 3–15 letters, and drawn from the project's vision and mechanics.\n\n"
        "You have only **3 guesses**, and **15 seconds** per guess. Good luck!"
    )
    
    # Check user limit
    can_play, current_users = check_user_limit()
    
    if not can_play:
        st.error("🚫 **Game is at capacity!**")
        st.write(f"Maximum {MAX_CONCURRENT_USERS} users can play simultaneously.")
        st.write(f"Currently **{current_users}/{MAX_CONCURRENT_USERS}** players online.")
        st.write("Please try again in a few minutes when someone finishes their game.")
        
        if st.button("🔄 Check Again"):
            st.rerun()
        return
    
    # Show current player count in sidebar
    st.sidebar.write(f"🎮 Players online: **{current_users}/{MAX_CONCURRENT_USERS}**")
    
    # Game start screen
    if not st.session_state.get("game_started", False):
        show_start_screen()
        return
    
  
    if "word" not in st.session_state:
        initialize_game()
    
    # Main game logic
    play_game()
    
    #  show restart button
    st.write("---")
    if st.button("🎮 Start New Game", use_container_width=True):
        reset_game()
        st.rerun()

def show_start_screen():
    """Display the game start screen"""
    st.markdown("### 🎯 Ready to Challenge Your Ethereum OS Knowledge?")
    st.write("This is **Hard Mode** - you'll face advanced terms from the Ethos ecosystem with:")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("- ⏰ Only **15 seconds** per guess")
        st.write("- 🎯 Just **3 attempts** total")
    with col2:
        st.write("- 🧠 You should know the Ethereum OS Vision")
        st.write("- 🏆 Rewards for winners!")
    
    st.write("")
    st.markdown("**Legend:**")
    legend_cols = st.columns(3)
    with legend_cols[0]:
        st.write("🟩 = Correct position")
    with legend_cols[1]:
        st.write("🟨 = Wrong position")
    with legend_cols[2]:
        st.write("⬜ = Not in word")
    
    st.write("")
    
    if st.button("🚀 Start Game", type="primary", use_container_width=True):
        initialize_game()
        st.rerun()

def play_game():
    """Main game play logic"""
    word_len = len(st.session_state.word)
    current_guess_elapsed = time.time() - st.session_state.guess_start_time
    
    # Check if game is finished
    if len(st.session_state.guesses) >= MAX_GUESSES or st.session_state.finished:
        st.session_state.finished = True
        show_game_results()
        return
    
    # Show game status
    remaining_time = max(0, GUESS_TIME_LIMIT - int(current_guess_elapsed))
    current_guess_num = len(st.session_state.guesses) + 1
    
    # Create status bar
    status_cols = st.columns(4)
    with status_cols[0]:
        st.metric("Word Length", word_len)
    with status_cols[1]:
        st.metric("Guess", f"{current_guess_num}/{MAX_GUESSES}")
    with status_cols[2]:
        st.metric("Time Left", f"{remaining_time}s")
    with status_cols[3]:
        if remaining_time <= 5:
            st.error("⏰ Hurry!")
        else:
            st.success("⏰ Active")
    
    # Show previous guesses
    if st.session_state.guesses:
        st.write("### Previous Guesses:")
        for i, (guess, fb) in enumerate(zip(st.session_state.guesses, st.session_state.feedback)):
            st.write(f"**Guess {i+1}:** {fb} `{guess}`")
        st.write("")
    
    # Handle time limit
    if current_guess_elapsed > GUESS_TIME_LIMIT:
        st.warning("⏰ Time's up for this guess!")
        st.session_state.guesses.append("(timed out)")
        st.session_state.feedback.append("⬜" * word_len)
        st.session_state.guess_start_time = time.time()
        
        if len(st.session_state.guesses) >= MAX_GUESSES:
            st.session_state.finished = True
        
        time.sleep(1)  
        st.rerun()
    
    # Input section
    with st.form(key=f"guess_form_{current_guess_num}"):
        guess = st.text_input(
            f"Enter guess {current_guess_num} (exactly {word_len} letters):",
            max_chars=word_len,
            placeholder=f"Type a {word_len}-letter word..."
        )
        
        submitted = st.form_submit_button("Submit Guess", type="primary", use_container_width=True)
        
        if submitted:
            process_guess(guess, word_len)
    
    # Auto-refresh for countdown
    if remaining_time > 0:
        time.sleep(1)
        st.rerun()

def process_guess(guess, word_len):
    """Process a submitted guess"""
    normalized_guess = normalize_word(guess)
    
    if len(normalized_guess) != word_len:
        st.error(f"⚠️ Please enter exactly {word_len} letters.")
        return
    
    if not normalized_guess:
        st.error("⚠️ Please enter a word.")
        return
    
    # Process the guess
    feedback = get_feedback(st.session_state.word, normalized_guess)
    st.session_state.guesses.append(guess)
    st.session_state.feedback.append(feedback)
    
    # Check if won
    if normalized_guess == st.session_state.word:
        st.session_state.game_won = True
        st.session_state.finished = True
    else:
        # Check if out of guesses
        if len(st.session_state.guesses) >= MAX_GUESSES:
            st.session_state.finished = True
    
    # Reset guess timer
    st.session_state.guess_start_time = time.time()
    st.rerun()

def show_game_results():
    """Display game results and handle winner submission"""
    st.write("### Your Guesses & Feedback:")
    
    for i, (guess, fb) in enumerate(zip(st.session_state.guesses, st.session_state.feedback)):
        st.write(f"**Guess {i+1}:** {fb} `{guess}`")
    
    if st.session_state.game_won:
        st.success("🎉 Congratulations! You won!")
        st.balloons()
        
        # Winner submission form
        st.write("### 🏆 Claim Your Reward")
        st.write("Enter your Twitter handle to receive your reward code:")
        
        with st.form("winner_form"):
            handle = st.text_input(
                "Twitter handle (without @):",
                placeholder="yourhandle"
            )
            
            submit_winner = st.form_submit_button("🎁 Submit for Reward", type="primary", use_container_width=True)
            
            if submit_winner and handle.strip():
                handle_winner_submission(handle.strip(), use_sheets=True)
            
            elif submit_winner and not handle.strip():
                st.error("⚠️ Please enter a valid Twitter handle.")
    
    else:
        st.error(f"💔 Game over! The word was: **`{st.session_state.word}`**")
        st.write("Better luck next time! Try again to test your blockchain knowledge.")

def handle_winner_submission(handle, use_sheets=True):
    """Handle winner submission to Google Sheets only"""
    if not SHEETS_AVAILABLE:
        st.error("❌ Google Sheets integration is not available. Please contact support.")
        return
        
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Google Sheets credentials not configured. Please contact support.")
        return
    
    with st.spinner("Submitting your entry..."):
        success, message = submit_to_google_sheets(handle)
    
    if success:
        st.success(f"✅ Your Twitter handle @{handle} has been submitted successfully!")
        st.info("🎁 Keep an eye on your Twitter DMs for your reward code!")
    else:
        st.error(f"❌ Submission failed: {message}")
        st.info("💡 Please try again or contact support if the issue persists.")


if __name__ == "__main__":
    main()

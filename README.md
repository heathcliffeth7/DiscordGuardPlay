# DiscordGuardPlay

DiscordGuardPlay is a comprehensive Discord bot that combines event management and security filtering functionalities. It enables seamless event participation by recording users’ in-game usernames in Excel files while enforcing automated security measures for new members based on profile avatar presence and account age.

## Features

### Event Management
- **Event Creation & Configuration:**
  - Create events with `!createplayevent`.
  - Set event-specific links using `!setplaylink`.
  - Designate channels for events with `!setplaychannel`.
- **Participation Tracking:**
  - Record in-game usernames in Excel files.
  - Limit repeated username entries via the `!samenicknamefilter` command.
  - Enforce role-based interaction limits using `!sendplaylimit`.
- **Interactive UI:**
  - Users can join events by clicking a “Play” button that opens a modal for entering their in-game username.

### Security Filters
- **No-Avatar Filter:**
  - Automatically ban, kick, or timeout users without a profile picture with the `!noavatarfilter` command.
- **Account Age Filter:**
  - Automatically apply actions to accounts that do not meet a specified age with the `!accountagefilter` command.
- **Authorization Controls:**
  - Restrict security commands to authorized roles or users.
  - Manage authorized users with `!securityauthorizedadd` and `!securityauthorizedremove`.

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/heathcliffeth7/DiscordGuardPlay.git
   cd DiscordGuardPlay
2.	Create and Activate a Virtual Environment:
     ```
     python -m venv venv
    # On Linux/macOS:
    source venv/bin/activate
    # On Windows:
    venv\Scripts\activate



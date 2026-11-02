#pragma once

// OpenSWBF2: a dedicated server's lobby is its pre-game held open until an admin starts the match
// (-lobby, rcon /start). Pre-game already keeps the AI out and stops timers, tickets and captures
// on every client, and its time reaches clients in 10 bits: the top value marks the lobby, so a
// client tells it from a countdown without a new packet field. No engine dependencies, so the unit
// tests can call it.
namespace NetLobby
{
const int kLobbyPreGameTime = 1023;
const int kMaxPreGameTime = 1000; // a real countdown never reaches the lobby marker

inline bool IsLobby(bool bPreGame, int iPreGameTime)
{
    return bPreGame && iPreGameTime == kLobbyPreGameTime;
}

inline int ClampPreGameTime(int iSeconds)
{
    return iSeconds < 0 ? 0 : (iSeconds > kMaxPreGameTime ? kMaxPreGameTime : iSeconds);
}

// A host leaves a finished match (an admin's /lobby now, /changemap, /restart, /endgame too) for
// the next map once everyone connected is playing (NetGame::IsGameOver). One still loading this
// map can't follow it there, since its load ack would read as loaded on the next map, so retail
// held the next map until it loaded or timed out, 60 s for a stuck one; the players already done
// went ahead and timed out waiting for it. Now one who isn't playing yet holds it this long after
// the host first asks, retail's cut-off for players sending stats who aren't playing; then the
// host drops it, and it joins again into the next map.
const float kGameOverJoinWait = 5.0f;

// fWaitStart: when the host first asked (NetComm time), 0 while the match runs
inline bool GameOverWaitDone(float fWaitStart, float fNow)
{
    return fWaitStart > 0.0f && fNow - fWaitStart > kGameOverJoinWait;
}
}

# All Known problems with the current Dominion build 
============================================================================

## General UI 

- Currently no way to restart or start a new game 
- Ui is not centered nor justified on the screen, and making a larger board does not auto-fit to the screen size.


## Frontend 

- start screen is lame, needs better theming, title, etc.. 
- Visible/moveable Plains tiles are still hidden by Fog of War.


## Backend 

- Wizard is shown at all times, but needs to be hidden by the Fog of War.
- Plains square is not currently working as intended; they should allow the player to take two consecutive blocks in any cardinal direction, or one block diagonal to the Plains.
- Barbs also not working as intended? 
    - Add debug statement to show when the Barbarians are triggered, and which way they charge.
- Caves should not give permanent access to all other Caves: once one Cave is used to travel to another Cave, those two Caves are considered connected and no longer have the special access quality.


## Things that could/should be added 

- Sound 
- Better visuals 
- multiplayer 
- rougelike portion/endless style mode 

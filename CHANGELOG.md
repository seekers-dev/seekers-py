# v0.1.1

- Update to api v0.1.2
- Split files into multiple smaller ones to improve maintainability
- Move files to new python packages
- Add cx_Freeze to create native wrapper binaries
- Move submodule
- Update pre-release workflow
- Update submodules

# v0.1.0

- Players can join via grpc to prevent unfair modification of game state by the AIs
- Implement a config.ini
- The magnet's status of disabled seekers in a collision is now always regarded as "off"
- Performance improvements
- Game length is no longer dependent on speed
- Debug drawing to assist in AI development
- AIs can now set a preferred colour
- AI colours are automatically adjusted if too similar

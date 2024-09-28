## v0.1.1

**Full Changelog**: https://github.com/seekers-dev/seekers-py/compare/v0.1.0...v0.1.1

### API

- Update to api v0.1.2

### Project

- Split files into multiple smaller ones to improve maintainability
- Move files to new python packages
- Add cx_Freeze to create native wrapper binaries
- Move submodule
- Update pre-release workflow
- Update submodules
- Add code of conduct

### Dependencies

- Bump grpcio from 1.59.3 to 1.64.1
- Bump protobuf from 4.23.2 to 5.27.2

## New Contributors

- @Supergecki made their first contribution in https://github.com/seekers-dev/seekers-py/pull/60
- @Kiyotoko made their first contribution in https://github.com/seekers-dev/seekers-py/pull/64
- @dependabot made their first contribution in https://github.com/seekers-dev/seekers-py/pull/74

## v0.1.0

**Full Changelog**: https://github.com/seekers-dev/seekers-py/commits/v0.1.0

### API

- Players can join via grpc to prevent unfair modification of game state by the AIs
- Implement a config.ini
- The magnet's status of disabled seekers in a collision is now always regarded as "off"
- Performance improvements
- Game length is no longer dependent on speed
- Debug drawing to assist in AI development
- AIs can now set a preferred color
- AI colors are automatically adjusted if too similar

### Dependencies

- Add grpcio
- Add protobuf

### New Contributors

- @Belissimo-T made their first contribution
- @joendter made their first contribution

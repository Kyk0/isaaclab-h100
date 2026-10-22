# Third-party content in `site/viewer/`

- `index.html`: the static web client of [viser](https://github.com/nerfstudio-project/viser) 1.1.1, built with `viser-build-client`. Apache License 2.0 (copy: [LICENSE-viser.txt](LICENSE-viser.txt)), © the viser authors.
- `g1_walk.viser`: a recording made with `scripts/replay_viser.py` from an Isaac Lab rollout of our G1 walking policy. It contains the Unitree G1 link meshes from NVIDIA's [GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl) (`gear_sonic/data/robots/g1/old/`, Apache License 2.0; robot model by Unitree Robotics), simplified to at most 3,000 triangles per mesh.

Unitree, G1 and NVIDIA are trademarks of their owners. Not affiliated with or endorsed by them.

# D-reader project

This was/is a project to create a functioning E-reader for my partner, which would also allow for an external trigger for page turning. The project has had two main iterations, sadly I didn't chronicle the first iteration very well and have few images of it intact, to add insult to injury the CAD program I used to design it was a student version so the files are now useless to me. This repo contains the redesign using FreeCAD in which a wooden case (instead of 3d printed PLA) is used, along with all the software for running it. 

![](photos/image%20(4).jpg) ![](photos/image%20(3).jpg)

I have tried to document the development process, source code and CAD/CAM. If you are interested these are split between the pages.

- [Requirement Analysis](https://dtourolle.github.io/requirement-analysis.html)
- [Mechanical Design and CAM](https://dtourolle.github.io/mechanical.html)
- [Electronics design](https://dtourolle.github.io/electronics.html)
- [Software design](https://dtourolle.github.io/software.html)
- [Lessons learnt](https://dtourolle.github.io/lessons.html)

# Acknowledgements

The project would have been impossible for me to complete without the OpenSource code created in the following projects:

- [IT8951 Display driver](https://github.com/GregDMeyer/IT8951)
- [Various bits of HTML parsing, inspiration for decoding EPUB](https://github.com/wustho/epr)
- [Micropython for the trigger device](https://micropython.org/)
- [Inspiration for powering the device one and off](https://github.com/NeonHorizon/lipopi)
- [ulab for fast maths on embedded devices](https://github.com/v923z/micropython-ulab)
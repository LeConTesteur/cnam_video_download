#! /usr/bin/env python3
"""
The main
"""

if __name__ == "__main__":
    import doit

    from cnam.video_downloader import dodo
    doit.run(dodo)

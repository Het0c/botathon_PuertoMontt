"""PyInstaller entrypoint; preserve absolute package imports."""
from server.app import main
import sys

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--ingest':
        del sys.argv[1]
        from server.bridge import main as ingest
        raise SystemExit(ingest())
    main()

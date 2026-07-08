from shared.db import get_db_connection
c=get_db_connection()
q="SELECT name FROM sqlite_master WHERE type='table' AND name in ('ResortBookings','ResortRoomPhotos','Notification','CancellationLog','Admin')"
rows=c.execute(q).fetchall()
print("tables:", [r[0] for r in rows])
c.close()

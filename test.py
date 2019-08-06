from tests_ import player
import time

avg = []

for a in range(1000):
    if a % 100 == 0:
        print(f"{a} tests...")
    start = time.perf_counter()
    player.run()
    avg.append((time.perf_counter()-start)*1000)
print(f"1000 loops done, avg {sum(avg)/len(avg):.2f} ms")

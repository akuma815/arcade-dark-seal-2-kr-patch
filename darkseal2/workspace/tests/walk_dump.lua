-- 상태 로드 후 자동 전진(P1 Up 유지) + 치트, 30프레임마다 레이어별 16x16 글자 타일 수 기록, pf3/pf4 에 글자가 뜨면 전체 덤프
local dir = "G:/Downloads/Korean Traslate Project/Games/Dark Seal/darkseal2/workspace/tests"
local log = io.open(dir .. "/walk_dump.log", "w")
local function L(s) log:write(s .. string.char(10)); log:flush() end
local n, dumped = 0, 0
local function count(base)
  local c = 0
  for i = 0, 2047 do
    local t = memory.readword(base + i * 2) % 4096
    if (t >= 0xa03 and t <= 0xb4b) or (t >= 0xdc2 and t < 0xe9c) then c = c + 1 end
  end
  return c
end
local function full(base, f)
  f:write(string.format("base %06x", base) .. string.char(10))
  for i = 0, 2047 do
    f:write(string.format("%04x ", memory.readword(base + i * 2)))
    if i % 64 == 63 then f:write(string.char(10)) end
  end
end
emu.registerafter(function()
  n = n + 1
  memory.writebyte(0xFDC026, 0x99); memory.writebyte(0xFDD004, 0x0C); memory.writebyte(0xFDD064, 0x02)
  memory.writebyte(0xFDD030, 0x50); memory.writebyte(0xFDD033, 0x3F)
  if n > 150 then
    local dirn = (math.floor(n / 240) % 2 == 0) and "P1 Up" or "P1 Right"
    joypad.set({[dirn] = true, ["P1 Fire 1"] = (n % 8 < 4)})
  end
  if n % 30 == 0 then
    local a, b, c, d = count(0x200000), count(0x202000), count(0x208000), count(0x20a000)
    L(string.format("f%05d pf0=%d pf1=%d pf2=%d pf3=%d", n, a, b, c, d))
    if (c > 0 or d > 0) and dumped < 3 then
      dumped = dumped + 1
      local f = io.open(dir .. string.format("/walk_full_%d.txt", dumped), "w")
      full(0x200000, f); full(0x208000, f); full(0x20a000, f); f:close()
      L("dumped " .. dumped)
    end
  end
end)
L("registered")

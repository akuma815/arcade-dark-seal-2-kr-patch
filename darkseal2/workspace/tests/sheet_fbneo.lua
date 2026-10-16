-- FBNeo: 8x8 타일 0x900~0xbff 를 pf1(0x200000) 에 격자로 써서 보여준다 (EKMAME autoboot_sheet.lua 와 동일 배치)
local n = 0
emu.registerafter(function()
  n = n + 1
  if n >= 240 and n <= 900 then
    local t = 0x900
    for row = 0, 15 do
      for col = 0, 47 do
        memory.writeword(0x200000 + (row + 4) * 128 + (col + 4) * 2, t)
        t = t + 1
      end
    end
  end
end)

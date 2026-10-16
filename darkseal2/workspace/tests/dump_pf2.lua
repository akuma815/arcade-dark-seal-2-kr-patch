-- 상태 로드 후 420프레임에 pf0(0x200000)·pf1(0x202000) 전체 2048워드를 파일로 기록
local out = io.open("G:/Downloads/Korean Traslate Project/Games/Dark Seal/darkseal2/workspace/tests/dump_pf2.txt", "w")
local n = 0
emu.registerafter(function()
  n = n + 1
  if n == 420 then
    for _, base in ipairs({0x200000, 0x202000, 0x208000, 0x20a000}) do
      out:write(string.format("base %06x", base) .. string.char(10))
      for i = 0, 2047 do
        out:write(string.format("%04x ", memory.readword(base + i * 2)))
        if i % 64 == 63 then out:write(string.char(10)) end
      end
    end
    out:flush(); out:close()
  end
end)

-- 레이어 덤프: 30프레임마다 pf0/pf1/pf2/pf3 RAM 에서 16x16 글자 타일(0xa03~0xb4b, 0xdc2~0xe9c)·쿼드 한글 타일(0x928~0xbff) 셀 수와 앞 24워드를 기록
local out = io.open("G:/Downloads/Korean Traslate Project/Games/Dark Seal/darkseal2/workspace/tests/dump_layers.log", "w")
local function L(s) out:write(s .. string.char(10)); out:flush() end
local bases = {0x200000, 0x202000, 0x208000, 0x20a000}
local n = 0
local function scan()
  for _, base in ipairs(bases) do
    local cnt16, cntq, words = 0, 0, {}
    for i = 0, 2047 do
      local w = memory.readword(base + i * 2)
      local t = w % 4096
      if (t >= 0xa03 and t <= 0xb4b) or (t >= 0xdc2 and t <= 0xe9c) then
        cnt16 = cnt16 + 1
        if #words < 24 then words[#words + 1] = string.format("%04x@%04x", w, i) end
      elseif base < 0x204000 and t >= 0x928 and t <= 0xbff then
        cntq = cntq + 1
      end
    end
    L(string.format("f%04d base=%06x font16=%d quad8=%d : %s", n, base, cnt16, cntq, table.concat(words, " ")))
  end
end
emu.registerafter(function()
  n = n + 1
  if n % 30 == 0 and n <= 1500 then scan() end
end)
L("registered")

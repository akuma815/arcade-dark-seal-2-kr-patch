-- Dark Seal 2 (darkseal2) 플레이 QA 용 치트. 주소는 FBNeo support/cheats/darkseal2.ini 그대로.
-- 무한 크레딧 · 1P 하트 무한 · 1P 무적 · 1P 아이템 전부(건틀릿 등 공격 보조 포함)
-- 추가: 키보드 K 를 누르면 보스 체력(0xFDDD05, ini 의 "Kill Dragon Now") 을 0 으로 — 보스전 즉시 종료용
-- 실행: python common/scripts/fbneo_play.py darkseal2 --ips kr --lua darkseal2/workspace/tests/cheat_qa.lua
local dir = "G:/Downloads/Korean Traslate Project/Games/Dark Seal/darkseal2/work"
local log = io.open(dir .. "/cheat_qa.log", "w")
local function L(s) log:write(tostring(s) .. "\n"); log:flush() end
L("input type: " .. type(input) .. (input and input.get and " (input.get ok)" or ""))
local killed = 0
emu.registerafter(function()
  memory.writebyte(0xFDC026, 0x99)  -- Infinite Credits
  memory.writebyte(0xFDD004, 0x0C)  -- Infinite Hearts PL1
  memory.writebyte(0xFDD064, 0x02)  -- Invincibility PL1
  -- memory.writebyte(0xFDD030, 0x50)  -- Maximum Magic PL1 (2026-10-05 사용자 요청으로 해제)
  memory.writebyte(0xFDD033, 0x3F)  -- All Items PL1
  if input and input.get then
    local ok, keys = pcall(input.get)
    if ok and keys and keys["K"] then
      memory.writebyte(0xFDDD05, 0x00)  -- Kill boss now
      killed = killed + 1
      if killed % 30 == 1 then L("K pressed: boss HP -> 0 (frame " .. emu.framecount() .. ")") end
    end
  end
end)

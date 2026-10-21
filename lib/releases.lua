local http = require("http")
local json = require("json")

local M = {}
local api = "https://api.github.com/repos/flix/flix/releases"

local function get(url)
    -- mise supplies GitHub authentication, when configured.
    local response, err = http.get({
        url = url,
        headers = { Accept = "application/vnd.github+json" },
    })
    if err ~= nil then
        error("mise-flix: could not fetch Flix releases: " .. tostring(err))
    end
    if response.status_code ~= 200 then
        local hint = ""
        if response.status_code == 403 or response.status_code == 429 then
            hint = "; check the GitHub API rate limit or configure MISE_GITHUB_TOKEN"
        end
        error("mise-flix: GitHub API returned HTTP " .. response.status_code .. hint)
    end
    return json.decode(response.body)
end

function M.jar(release)
    for _, asset in ipairs(release.assets or {}) do
        if asset.name == "flix.jar" then
            return asset
        end
    end
end

function M.available()
    local versions = {}
    local page = 1
    while true do
        local releases = get(api .. "?per_page=100&page=" .. page)
        for _, release in ipairs(releases) do
            if not release.draft and not release.prerelease and M.jar(release) then
                local version = release.tag_name:match("^v(%d+%.%d+%.%d+)$")
                if version then
                    table.insert(versions, { version = version, created_at = release.published_at })
                end
            end
        end
        if #releases < 100 then
            break
        end
        page = page + 1
    end
    return versions
end

function M.download(version)
    local os_type = RUNTIME.osType:lower()
    if os_type ~= "darwin" and os_type ~= "linux" then
        error("mise-flix: currently supports macOS and Linux")
    end
    if not version:match("^%d+%.%d+%.%d+$") then
        error("mise-flix: expected a stable Flix version such as 0.79.0")
    end

    local release = get(api .. "/tags/v" .. version)
    if release.draft or release.prerelease then
        error("mise-flix: only stable Flix releases are supported")
    end
    local asset = M.jar(release)
    if not asset then
        error("mise-flix: release v" .. version .. " does not contain flix.jar")
    end

    local sha256
    if type(asset.digest) == "string" and asset.digest ~= "" then
        sha256 = asset.digest:match("^sha256:(%x+)$")
        if not sha256 or #sha256 ~= 64 then
            error("mise-flix: invalid SHA-256 digest for v" .. version)
        end
    end
    return { version = version, url = asset.browser_download_url, sha256 = sha256 }
end

return M

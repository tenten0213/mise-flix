package.path = "./lib/?.lua;" .. package.path

local responses = {}
local requested = {}
package.preload["http"] = function()
    return {
        get = function(opts)
            table.insert(requested, opts.url)
            assert(responses[opts.url], "unexpected request: " .. opts.url)
            return responses[opts.url]
        end,
    }
end
package.preload["json"] = function()
    return {
        decode = function(body)
            return body
        end,
    }
end
package.preload["file"] = function()
    return {
        join_path = function(...)
            return table.concat({ ... }, "/")
        end,
    }
end

dofile("metadata.lua")
dofile("hooks/available.lua")
dofile("hooks/pre_install.lua")
dofile("hooks/env_keys.lua")
RUNTIME = { osType = "darwin" }

local api = "https://api.github.com/repos/flix/flix/releases"
local digest = string.rep("a", 64)
local count = 0

local function release(version)
    return {
        tag_name = "v" .. version,
        published_at = "2026-10-18T10:38:39Z",
        assets = {
            {
                name = "flix.jar",
                browser_download_url = "https://github.com/flix/flix/releases/download/v"
                    .. version
                    .. "/flix.jar",
                digest = "sha256:" .. digest,
            },
        },
    }
end

local function respond(url, body, status)
    responses[url] = { status_code = status or 200, body = body }
end

local function expect_error(message, fn)
    local ok, err = pcall(fn)
    assert(not ok, "expected an error")
    assert(tostring(err):find(message, 1, true), tostring(err))
    return tostring(err)
end

local function test(name, fn)
    responses = {}
    requested = {}
    RUNTIME.osType = "darwin"
    fn()
    count = count + 1
    print("ok - " .. name)
end

test("lists only stable releases with a JAR and preserves release dates", function()
    local prerelease = release("0.80.0")
    prerelease.prerelease = true
    local draft = release("0.81.0")
    draft.draft = true
    local no_jar = release("0.76.0")
    no_jar.assets = { { name = "sources.zip" } }
    respond(api .. "?per_page=100&page=1", {
        draft,
        prerelease,
        release("0.79.0"),
        release("0.78.0"),
        no_jar,
        release("nightly"),
    })
    local versions = PLUGIN:Available({})
    assert(#versions == 2)
    assert(versions[1].version == "0.79.0")
    assert(versions[2].version == "0.78.0")
    assert(versions[1].created_at == "2026-10-18T10:38:39Z")
end)

test("fetches older releases beyond the first page", function()
    local first_page = {}
    for i = 100, 1, -1 do
        table.insert(first_page, release("0." .. i .. ".0"))
    end
    respond(api .. "?per_page=100&page=1", first_page)
    respond(api .. "?per_page=100&page=2", { release("0.0.1") })
    local versions = PLUGIN:Available({})
    assert(#versions == 101)
    assert(versions[101].version == "0.0.1")
    assert(#requested == 2)
end)

test("returns the upstream JAR URL and SHA-256", function()
    respond(api .. "/tags/v0.79.0", release("0.79.0"))
    local download = PLUGIN:PreInstall({ version = "0.79.0" })
    assert(download.version == "0.79.0")
    assert(download.url == release("0.79.0").assets[1].browser_download_url)
    assert(download.sha256 == digest)
end)

test("accepts older releases without a publisher digest", function()
    local old = release("0.30.0")
    old.assets[1].digest = nil
    respond(api .. "/tags/v0.30.0", old)
    assert(PLUGIN:PreInstall({ version = "0.30.0" }).sha256 == nil)
end)

test("rejects malformed digests instead of skipping verification", function()
    local broken = release("0.79.0")
    broken.assets[1].digest = "sha256:not-a-valid-digest"
    respond(api .. "/tags/v0.79.0", broken)
    expect_error("invalid SHA-256", function()
        PLUGIN:PreInstall({ version = "0.79.0" })
    end)
end)

test("rejects releases without flix.jar", function()
    respond(api .. "/tags/v0.79.0", { assets = {} })
    expect_error("does not contain flix.jar", function()
        PLUGIN:PreInstall({ version = "0.79.0" })
    end)
end)

test("rejects prereleases even when explicitly requested", function()
    local pre = release("0.79.0")
    pre.prerelease = true
    respond(api .. "/tags/v0.79.0", pre)
    expect_error("only stable", function()
        PLUGIN:PreInstall({ version = "0.79.0" })
    end)
end)

test("reports API failures without exposing the response body", function()
    respond(api .. "?per_page=100&page=1", "private response body", 403)
    local err = expect_error("HTTP 403", function()
        PLUGIN:Available({})
    end)
    assert(err:find("MISE_GITHUB_TOKEN", 1, true))
    assert(not err:find("private response body", 1, true))
end)

test("rejects unsupported operating systems before downloading", function()
    RUNTIME.osType = "windows"
    expect_error("macOS and Linux", function()
        PLUGIN:PreInstall({ version = "0.79.0" })
    end)
    assert(#requested == 0)
end)

test("rejects invalid version requests before making an API call", function()
    expect_error("expected a stable Flix version", function()
        PLUGIN:PreInstall({ version = "../../other" })
    end)
    assert(#requested == 0)
end)

test("adds only the launcher directory and leaves Java selection alone", function()
    local keys = PLUGIN:EnvKeys({ path = "/tmp/mise with spaces/flix/0.79.0" })
    assert(#keys == 1)
    assert(keys[1].key == "PATH")
    assert(keys[1].value == "/tmp/mise with spaces/flix/0.79.0/bin")
    assert(PLUGIN.depends[1] == "java")
end)

print(count .. " hook tests passed")

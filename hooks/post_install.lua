local function quote(value)
    return "'" .. value:gsub("'", "'\\''") .. "'"
end

function PLUGIN:PostInstall(ctx)
    local cmd = require("cmd")
    local file = require("file")
    local root = ctx.rootPath
    local bin = file.join_path(root, "bin")
    local lib = file.join_path(root, "lib")
    cmd.exec("mkdir -p " .. quote(bin) .. " " .. quote(lib))

    local downloaded = file.join_path(root, "flix.jar")
    local jar = file.join_path(lib, "flix.jar")
    if file.exists(downloaded) then
        assert(os.rename(downloaded, jar))
    end
    if not file.exists(jar) then
        error("mise-flix: download did not contain flix.jar")
    end

    local source = file.join_path(RUNTIME.pluginDirPath, "scripts", "flix")
    local launcher = file.join_path(bin, "flix")
    local output = assert(io.open(launcher, "wb"))
    assert(output:write(file.read(source)))
    assert(output:close())
    cmd.exec("chmod 755 " .. quote(launcher))
end

function PLUGIN:PreInstall(ctx)
    return require("releases").download(ctx.version)
end

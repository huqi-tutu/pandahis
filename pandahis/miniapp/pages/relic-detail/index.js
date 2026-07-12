Page({
    data: {
        name: '',
        museum: '',
        detail: '',
        imageUrl: '',
        headerPadPx: 88,
    },
    onLoad(query) {
        try {
            const sys = wx.getSystemInfoSync();
            const navPx = 88 * (sys.windowWidth / 750);
            this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx });
        }
        catch {
            this.setData({ headerPadPx: 88 });
        }
        this.setData({
            name: decodeURIComponent(query.name || ''),
            museum: decodeURIComponent(query.museum || ''),
            detail: decodeURIComponent(query.detail || ''),
            imageUrl: decodeURIComponent(query.imageUrl || ''),
        });
    },
});

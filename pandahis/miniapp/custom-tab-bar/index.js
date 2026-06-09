Component({
    data: {
        selected: 0,
        list: [
            { pagePath: '/pages/home/index' },
            { pagePath: '/pages/search/index' },
            { pagePath: '/pages/invite/index' },
            { pagePath: '/pages/my/index' },
        ],
    },
    methods: {
        setSelected(index) {
            this.setData({ selected: index });
        },
        onTap(e) {
            const indexStr = e.currentTarget.dataset.index;
            const index = Number(indexStr);
            const item = this.data.list[index];
            if (!item)
                return;
            wx.switchTab({ url: item.pagePath });
        },
    },
});

"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../native-utils/api");
const router_1 = require("../native-utils/router");
const INVITE_TAB_INDEX = 2;
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
            if (index === INVITE_TAB_INDEX && !(0, api_1.hasToken)()) {
                (0, router_1.navigateTo)(router_1.ROUTES.login, { from: 'invite' });
                return;
            }
            wx.switchTab({ url: item.pagePath });
        },
    },
});

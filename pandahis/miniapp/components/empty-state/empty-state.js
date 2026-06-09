Component({
    properties: {
        type: { type: String, value: 'search' },
        title: { type: String, value: '暂无内容' },
        desc: { type: String, value: '' },
        cta: { type: String, value: '' },
    },
    methods: {
        onCta() {
            this.triggerEvent('cta');
        },
    },
});

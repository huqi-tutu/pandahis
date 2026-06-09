const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();

exports.main = async (event, context) => {
  // 测试：插入一条带所有字段的测试记录
  const testRecord = {
    '历史盒子 ID': 'test_001',
    '帝王': '测试',
    '政权': '测试',
    '朝代': '测试',
    '文明': '测试',
    '帝王名字': '测试',
    '庙号': '-',
    '年号': '-',
    '即位时间': '-',
    '退位时间': '-',
    '在位时长': '0',
    '重要性评级': '1',
    '标签': '测试标签'
  };
  
  try {
    const result = await db.collection('test_collection').add({ data: testRecord });
    return { success: true, _id: result._id, message: '测试成功，集合 test_collection 已创建' };
  } catch (err) {
    return { success: false, error: err.message || String(err) };
  }
};

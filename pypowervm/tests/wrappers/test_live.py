# import unittest
# 
# from pypowervm import adapter
# from pypowervm.jobs import wwpn
# from pypowervm.wrappers import logical_partition as pvm_lpar
# from pypowervm.wrappers import virtual_io_server as pvm_vios
# 
# 
# class TestLive(unittest.TestCase):
# 
#     def setUp(self):
#         super(TestLive, self).setUp()
#         sess = adapter.Session("9.114.181.152", "hscroot", "Passw0rd",
#                                certpath=None)
#         self.adpt = adapter.Adapter(sess)
# 
#     def testMapping(self):
#         host_uuid = 'c5d782c7-44e4-3086-ad15-b16fb039d63b'
#         vios_uuid = '3443DB77-AED1-47ED-9AA5-3DB9C6CF7089'
#         client_uuid = '3B0237F9-26F1-41C7-BE57-A08C9452AD9D'
# 
#         vio_resp = self.adpt.read('VirtualIOServer', root_id=vios_uuid)
#         vio_w = pvm_vios.VIOS.wrap(vio_resp)
# 
#         my_wwpns = wwpn.build_wwpn_pair(self.adpt, host_uuid)
# 
#         print vio_w.vfc_mappings
# 
#         vfc_mapping = pvm_vios.VFCMapping.bld(self.adpt, host_uuid,
#                                               client_uuid, 'fcs0')
# 
#         print vfc_mapping.backing_port
# 
#         vio_w.vfc_mappings.append(vfc_mapping)
# #         try:
# #             self.adpt.update(vio_w, vio_w.etag, 'VirtualIOServer',
# #                              root_id=vios_uuid)
# #         except Exception as e:
# #             print e.response.body
# #             raise
# 
#         pass
